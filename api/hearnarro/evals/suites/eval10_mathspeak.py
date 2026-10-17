"""EVAL-10 Spoken mathematics: is an equation read as a person would read it aloud?
(MATH-1 to MATH-4; PRD "Evals"; spec ``_agent/specs/m5-academic-reading.md`` §1b, §1c)

Two kinds of example:

- one per pair of ``evals/data/math_speech.jsonl``: ``id``, ``class`` (``display``, ``inline``,
  ``symbol``, ``reference``), ``raw`` (the text as a PDF would carry it), ``spoken`` (how a careful
  narrator reads it, written by hand in the spec §3c convention) and ``block`` (``equation`` or
  ``body``). ``raw`` is turned into a stage-1 ``Block`` with span geometry (``_blocks``):
  Unicode scripts (``x²``, ``xᵢ``) stay characters; ``^{...}`` becomes a superscript span
  (smaller, raised, ``superscript=True``) and ``_{...}`` a subscript span (smaller, lowered);
  a line break in an equation block stacks the lines (numerator over denominator); in a body
  block ``$...$`` marks a maths-font run (CMMI10, italic), the rest is Helvetica. An equation
  block is all maths font. The block then goes through the app's own ``merge_blocks`` and
  ``split_sentences`` and, when ``hearnarro.ingestion.mathspeak`` exists (phase 3),
  ``apply_mathspeak``; the actual text is every segment's ``normalized_text``.
- one per formula fixture (manifest ``class`` ``formula``, spec §1a), ``class`` ``fixture``:
  the actual text is the ``normalized_text`` of ``math_segments(result)`` (equation segments plus
  segments with a non-empty ``math_spans``) of the cached ``ingest()``; the expected text is the
  non-comment lines of ``<stem>.spoken.txt``. A fixture without a spoken.txt, or an image-only
  page while no OCR engine is available, is skipped with the reason.

Score: ``scorers.mathspeak_score`` (D14-style word-sequence score, lowercased, punctuation
stripped, clamped at 0), the function the M5 gate test uses. Aggregate: mean, min and the mean
``by_class``.
"""

from __future__ import annotations

import json
from functools import cache
from pathlib import Path
from typing import Any

from hearnarro.evals.scorers import mathspeak_score
from hearnarro.evals.suites import _fixtures

ID = "EVAL-10"
TITLE = "Spoken mathematics"
TIER = 0
DIRECTION = "higher"

DATA = Path(__file__).resolve().parents[1] / "data" / "math_speech.jsonl"
CLASSES = ("display", "inline", "symbol", "reference", "fixture")
FORMULA_CLASS = "formula"


@cache
def load_pairs() -> tuple[dict[str, Any], ...]:
    """Every pair of ``math_speech.jsonl``, in file order."""
    lines = DATA.read_text(encoding="utf-8").splitlines()
    return tuple(json.loads(line) for line in lines if line.strip())


def _blocks(raw: str, block: str) -> list[Any]:
    """One stage-1 ``Block`` holding ``raw`` with span geometry: the markup helper shared with the
    mathspeak unit tests (``hearnarro.ingestion.mathspeak.markup``, docstring above)."""
    from hearnarro.ingestion.mathspeak.markup import markup_blocks

    return markup_blocks(raw, block)


def _mathspeak() -> Any:
    """The phase-3 package ``hearnarro.ingestion.mathspeak``, or None before it lands."""
    try:
        from hearnarro.ingestion import mathspeak
    except ImportError:
        return None
    return mathspeak


def spoken(raw: str, block: str) -> str:
    """The text the app sends to the voice for one ``math_speech.jsonl`` pair."""
    from hearnarro.ingestion.merge import merge_blocks
    from hearnarro.ingestion.segment import split_sentences

    logical = merge_blocks(_blocks(raw, block))
    segments = []
    for lb in logical:
        segments.extend(
            split_sentences(lb, document_id=0, order_start=len(segments), id_start=len(segments))
        )
    ms = _mathspeak()
    if ms is not None and hasattr(ms, "apply_mathspeak"):
        ms.apply_mathspeak(segments, logical, [], None)
    return " ".join(s.normalized_text for s in segments)


def math_segments(result: Any) -> list[Any]:
    """Segments that hold mathematics, in order: ``mathspeak.math_segments`` once phase 3 lands,
    else equation segments plus segments with a non-empty ``math_spans`` (spec §1c, §3a)."""
    ms = _mathspeak()
    if ms is not None and hasattr(ms, "math_segments"):
        return list(ms.math_segments(result))
    by_id = {b.id: b for b in result.blocks}
    return [
        s
        for s in result.segments
        if by_id[s.block_id].type == "equation" or getattr(s, "math_spans", None)
    ]


def formula_entries() -> list[dict[str, Any]]:
    """Manifest entries of the M5 formula fixtures (spec §1a), in manifest order."""
    return [e for e in _fixtures.manifest() if e.get("class") == FORMULA_CLASS]


@cache
def has_text_layer(name: str) -> bool:
    """True when any page of ``<name>.pdf`` carries extractable text (ING-2)."""
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(str(_fixtures.FIXTURES / f"{name}.pdf"))
    try:
        return any(page.get_textpage().get_text_range().strip() for page in pdf)
    finally:
        pdf.close()


def spoken_lines(name: str) -> list[str]:
    """Expected spoken lines of ``<name>.spoken.txt``: non-empty, ``#`` comments dropped."""
    path = _fixtures.FIXTURES / f"{name}.spoken.txt"
    lines = path.read_text(encoding="utf-8").splitlines()
    return [ln.strip() for ln in lines if ln.strip() and not ln.lstrip().startswith("#")]


def fixture_actual(name: str) -> list[str]:
    """``normalized_text`` of the maths segments of the cached ingest of fixture ``name``."""
    return [s.normalized_text for s in math_segments(_fixtures.ingest_result(name))]


def fixture_score(name: str) -> float:
    """The EVAL-10 / gate (b) score of one formula fixture."""
    return mathspeak_score(fixture_actual(name), spoken_lines(name))


def _fixture_skip(name: str) -> str | None:
    from hearnarro.ingestion.extract import ocr_available

    for suffix in (".pdf", ".spoken.txt"):
        if not (_fixtures.FIXTURES / f"{name}{suffix}").exists():
            return f"missing fixture file {name}{suffix}"
    if not has_text_layer(name) and not ocr_available():
        return "image-only fixture and no OCR engine on PATH (ING-2)"
    return None


def dataset() -> list[dict[str, Any]]:
    """One example per pair, then one per formula fixture."""
    out: list[dict[str, Any]] = [dict(p, skip=None) for p in load_pairs()]
    for e in formula_entries():
        name = e["name"]
        out.append({"id": name, "class": "fixture", "name": name, "skip": _fixture_skip(name)})
    return out


def score(example: dict[str, Any]) -> dict[str, Any]:
    """id, class, score, actual, expected (and ``text_layer`` for a fixture)."""
    if example["class"] == "fixture":
        name = example["name"]
        actual, expected = fixture_actual(name), spoken_lines(name)
        return {
            "id": example["id"],
            "class": "fixture",
            "score": mathspeak_score(actual, expected),
            "text_layer": has_text_layer(name),
            "actual": " | ".join(actual),
            "expected": " | ".join(expected),
        }
    actual = spoken(example["raw"], example["block"])
    return {
        "id": example["id"],
        "class": example["class"],
        "score": mathspeak_score([actual], [example["spoken"]]),
        "actual": actual,
        "expected": example["spoken"],
    }


def aggregate(scores: list[dict[str, Any]]) -> dict[str, Any]:
    """Mean and min score overall, and the mean per class (display, inline, symbol, reference,
    fixture; a class with no scored example is left out)."""
    if not scores:
        return {"mean": 0.0, "min": 0.0, "by_class": {}}
    by: dict[str, list[float]] = {}
    for s in scores:
        by.setdefault(s["class"], []).append(s["score"])
    values = [s["score"] for s in scores]
    return {
        "mean": sum(values) / len(values),
        "min": min(values),
        "by_class": {c: sum(by[c]) / len(by[c]) for c in CLASSES if c in by},
    }
