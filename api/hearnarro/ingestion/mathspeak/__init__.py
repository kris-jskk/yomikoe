"""Mathspeak: spoken mathematics from span geometry (MATH-1..4, D36, D37; spec §3b).

``speak_segment`` is the pure core: it rewrites one segment's text into what the voice reads and
the ``char_map`` back into the text. Maths spans are parsed (``structure.parse``) and spoken
(``reader.speak``), or read by ``reader.fallback`` when they cannot be structured; prose between
them gets the MATH-4 reference rewrites (``references``) and the MATH-3 unit and chemistry
rewrites (``symbols.rewrite_units``), and the rest goes through stage 5's ``normalize`` unchanged.

``char_map`` rule (D36): a rewritten stretch ``text[start:start + L]`` spoken as ``E`` (length
L') maps output char k to ``start + min(L - 1, k * L // L')``, the formula ``normalize`` uses for
a rewritten token: monotone, every output char inside its span. A numbered display is spoken
"equation 3: ..." over the whole span, so the map stays monotone (the prefix maps onto the
span's first characters rather than onto the trailing "(3)").

``apply_mathspeak`` is the step after stage 5 (not yet called by ``ingest``): per segment it
clips the block's ``math_spans`` to the segment, calls ``speak_segment`` and stores
``Segment.math_json`` as ``[{start, end, display, label, tree}]`` (``tree`` the serialised
``Node`` or None after a fallback), from which ``speak_segment`` re-runs without the PDF.
"""

from __future__ import annotations

import itertools
import re
from collections.abc import Iterable, Sequence
from dataclasses import replace
from typing import Any

from hearnarro.ingestion.mathspeak.reader import fallback, prefix, speak
from hearnarro.ingestion.mathspeak.references import rewrite_references
from hearnarro.ingestion.mathspeak.structure import MathSpan, Node, label_of, parse
from hearnarro.ingestion.mathspeak.symbols import name_of, rewrite_units
from hearnarro.ingestion.normalize import normalize
from hearnarro.ingestion.profile import PROSE_DEFAULT, DocumentProfile

__all__ = [
    "apply_mathspeak",
    "char_map_errors",
    "glyph_spans",
    "math_segments",
    "speak_segment",
    "speak_span",
]


def speak_span(
    span: MathSpan | dict[str, Any], text: str, *, intervals: bool = True
) -> tuple[str, dict[str, Any]]:
    """Spoken English for one maths span of ``text`` and its ``math_json`` entry."""
    if isinstance(span, dict):
        start, end, display = span["start"], span["end"], span.get("display", False)
        label = span.get("label")
        tree = Node.from_json(span["tree"]) if span.get("tree") else None
        stand_in = MathSpan(start, end, display, [], label)
    else:
        start, end, display, label = span.start, span.end, span.display, span.label
        # A span's own leading or trailing whitespace stays with the prose around it, so the
        # spoken maths does not glue onto the next word ("k sub 2we").
        while start < end - 1 and text[start].isspace():
            start += 1
        while end > start + 1 and text[end - 1].isspace():
            end -= 1
        raw = text[start:end]
        if display and label is None:
            label = label_of(raw)
        stand_in = replace(span, start=start, end=end, label=label)
        tree = parse(stand_in, raw)
    spoken = speak(tree, intervals=intervals).strip() if tree is not None else ""
    if not spoken:
        tree = None
        spoken = fallback(stand_in, text[start:end])
    elif display:
        spoken = prefix(label) + spoken
    entry = {
        "start": start,
        "end": end,
        "display": display,
        "label": label,
        "tree": tree.to_json() if tree is not None else None,
    }
    return spoken, entry


def _speak(
    text: str, math_spans: Sequence[MathSpan | dict[str, Any]], profile: DocumentProfile | None
) -> tuple[str, list[int], list[dict[str, Any]]]:
    intervals = profile is None or profile.effective != "prose"
    norm_profile = profile or PROSE_DEFAULT
    edits: list[tuple[int, int, str]] = []
    entries: list[dict[str, Any]] = []

    def key(s: MathSpan | dict[str, Any]) -> int:
        return s["start"] if isinstance(s, dict) else s.start

    for span in sorted(math_spans, key=key):
        spoken, entry = speak_span(span, text, intervals=intervals)
        s, e = entry["start"], entry["end"]
        if not (0 <= s < e <= len(text)) or (edits and s < edits[-1][1]):
            continue
        edits.append((s, e, spoken))
        entries.append(entry)
    for s, e, spoken in rewrite_references(text) + rewrite_units(text):
        if not any(s < b and a < e for a, b, _ in edits):
            edits.append((s, e, spoken))
    edits.sort()
    out: list[str] = []
    cmap: list[int] = []
    pos = 0

    def plain(a: int, b: int) -> None:
        if a < b:
            norm, m = normalize(text[a:b], profile=norm_profile)
            out.append(norm)
            cmap.extend(a + i for i in m)

    for s, e, spoken in edits:
        plain(pos, s)
        length, n = e - s, len(spoken)
        out.append(spoken)
        cmap.extend(s + min(length - 1, k * length // n) for k in range(n))
        pos = e
    plain(pos, len(text))
    return "".join(out), cmap, entries


def speak_segment(
    text: str,
    math_spans: Sequence[MathSpan | dict[str, Any]],
    profile: DocumentProfile | None = None,
) -> tuple[str, list[int]]:
    """(normalized_text, char_map) for one segment: ``math_spans`` (offsets into ``text``, as
    ``MathSpan`` or ``math_json`` entries) spoken, prose normalized (module docstring). A
    ``prose`` profile reads bracket pairs in maths as lists; None means unspecified."""
    spoken, cmap, _ = _speak(text, math_spans, profile)
    return spoken, cmap


def apply_mathspeak(
    segments: list[Any],
    blocks: Iterable[Any],
    pages: Iterable[Any],
    profile: DocumentProfile | None,
) -> None:
    """Rewrite ``normalized_text`` / ``char_map`` and set ``math_json`` on every segment whose
    text holds maths, an equation reference or a unit (module docstring). ``pages`` is unused
    today (span geometry is carried on ``MathSpan.runs``)."""
    del pages
    by_id = {b.id: b for b in blocks}
    for seg in segments:
        block = by_id.get(seg.block_id)
        local: list[MathSpan] = []
        for sp in getattr(block, "math_spans", None) or []:
            s, e = max(sp.start, seg.char_start), min(sp.end, seg.char_end)
            if s >= e:
                continue
            inside = sp.start >= seg.char_start and sp.end <= seg.char_end
            local.append(
                replace(
                    sp,
                    start=s - seg.char_start,
                    end=e - seg.char_start,
                    runs=sp.runs if inside else [],
                )
            )
        if getattr(block, "type", None) not in ("table", "code"):
            local.extend(glyph_spans(seg.text, local))
        if not local and not rewrite_references(seg.text) and not rewrite_units(seg.text):
            continue
        seg.normalized_text, seg.char_map, entries = _speak(seg.text, local, profile)
        seg.math_json = entries or None


_TOKEN = re.compile(r"\S+")
_EDGE_PUNCT = ".,;:!?"


def glyph_spans(text: str, spans: Sequence[MathSpan] = ()) -> list[MathSpan]:
    """Inline spans (no runs) over the whitespace tokens of ``text`` that hold a non-ASCII
    character named by the MATH-3 table and lie outside ``spans``: maths set in a text font
    ("prior Π", "θ ∈Θ") has no math-font run for ``merge_blocks`` to mark (MATH-2, MATH-3).
    Sentence punctuation and an unmatched bracket at either end stay with the prose; a token the
    unit or reference rewrites already cover is left to them."""
    out: list[MathSpan] = []
    taken = [(a, b) for a, b, _ in rewrite_units(text) + rewrite_references(text)]
    taken += [(sp.start, sp.end) for sp in spans]
    for m in _TOKEN.finditer(text):
        s, e = m.start(), m.end()
        while e > s and text[e - 1] in _EDGE_PUNCT:
            e -= 1
        tok = text[s:e]
        if not tok:
            continue
        if tok[-1] in ")]" and tok.count(tok[-1]) > tok.count("(" if tok[-1] == ")" else "["):
            e -= 1
        if tok[0] in "([" and tok.count(tok[0]) > tok.count(")" if tok[0] == "(" else "]"):
            s += 1
        if s >= e or any(s < b and a < e for a, b in taken):  # units ("10 μm") stay MATH-3
            continue
        if any(not c.isascii() and name_of(c) for c in text[s:e]):
            out.append(MathSpan(s, e, False, []))
    return out


def math_segments(result: Any) -> list[Any]:
    """Segments that hold mathematics, in order: equation segments and segments with maths spans."""
    by_id = {b.id: b for b in result.blocks}
    return [
        s
        for s in result.segments
        if by_id[s.block_id].type == "equation" or getattr(s, "math_json", None)
    ]


def char_map_errors(
    text: str, out: str, cmap: list[int], spans: Sequence[MathSpan | dict[str, Any]]
) -> list[str]:
    """Violations of the D36 ``char_map`` rule for one ``speak_segment`` result (empty when it
    holds): lengths agree, the map is monotone and inside ``text``, and the output characters that
    map into each maths span form one contiguous run equal to that span's spoken text."""
    errors: list[str] = []
    if len(cmap) != len(out):
        errors.append(f"len(char_map) {len(cmap)} != len(text) {len(out)}")
    if any(not 0 <= i < len(text) for i in cmap):
        errors.append("index outside the source text")
    if any(a > b for a, b in itertools.pairwise(cmap)):
        errors.append("not monotone")
    for span in spans:
        s, e = (span["start"], span["end"]) if isinstance(span, dict) else (span.start, span.end)
        idx = [k for k, i in enumerate(cmap) if s <= i < e]
        if not idx or idx != list(range(idx[0], idx[-1] + 1)):
            errors.append(f"span {s}:{e} output is empty or not contiguous")
        elif out[idx[0] : idx[-1] + 1] != speak_span(span, text)[0]:
            errors.append(f"span {s}:{e} output is not its spoken text")
    return errors
