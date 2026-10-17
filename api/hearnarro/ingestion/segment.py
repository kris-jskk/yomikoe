"""Stage 5: sentence segmentation with offsets into the logical block (D4, ING-5).

pysbd proposes sentence spans; three passes over the spans then correct it, all on
``(start, end)`` offsets into ``block.text`` so ``block.text[start:end] == segment.text`` holds
by construction:

1. closers: a span that starts with closing quotes or brackets gives them to the previous span
   (``“stop.” Then`` keeps ``”`` with ``stop.``);
2. merges: a span is joined to the previous one when the split follows a known abbreviation
   (``abbreviations.py``), a section number (``2.1.``), an initial (``(P. Smith``, ``W. Q.``,
   ``[9] R.``), or an unterminated span followed by a lowercase or digit start, or by a
   bracket that is maths notation or closes an open bracket (pysbd's list-item rule splits
   ``PA (i), CH (i)`` and ``(System 1)``; a real list item ``and (ii) when`` stays split), or
   when the next span starts with ``,`` ``;`` or a hyphen, or after ``www.`` before a host
   (``at www. ericpartaker.com``, a line break inside a web address); a pysbd split inside a token
   with word characters on both sides is left alone (word-level golden, see ``_merge``);
3. letter splits: a one-letter variable after a lowercase word (not ``and``, not inside a
   ``[n]`` reference entry) ends a sentence before a capital (``kernel P. Its``), which
   pysbd's single-letter rule never splits.
"""

from __future__ import annotations

import re
from functools import cache

import pysbd

from hearnarro.ingestion.abbreviations import DEFAULT_ABBREVIATIONS, AbbreviationSet
from hearnarro.ingestion.models import LogicalBlock, Segment
from hearnarro.ingestion.normalize import normalize
from hearnarro.ingestion.profile import PROSE_DEFAULT, DocumentProfile

Span = tuple[int, int]

_CLOSERS = re.compile(r"(?:[”’»)\]}]|[\"'](?=\s|$))+")
_SECTION_NUMBER = re.compile(r"\d+(?:\.\d+)*\.")
_INITIAL = re.compile(r"\(?-?[A-Z]\.(?:-?[A-Z]\.)*")
_REFERENCE_MARKER = re.compile(r"\[\d+\]")
_REFERENCE_ENTRY = re.compile(r"\[\d+\]\s+[“\"(]?[A-Z]")
_NUMBERED_ITEM = re.compile(r"\d+\.\s")
_DOMAIN_START = re.compile(r"[\w-]+\.[a-z]")
_OPENERS = "([{“\"‘'"
_TERMINAL = ".!?…:;"
_TRAILING_CLOSERS = ")]}”’\"'»"
# "<word> <letter>. <Capital>": a candidate one-letter-variable sentence end.
_LETTER_END = re.compile(r"(?P<prev>\S+)\s+[A-Za-z]\.(?=\s+[“\"(]?[A-Z])")
_PLAIN_WORD = re.compile(r"[A-Za-z][a-z]+[,.]?")
_LETTER_PREV = re.compile(r"[a-z][\w\-]*")
_LETTER_PREV_WORDS = frozenset(
    {"Appendix", "Section", "Part", "Figure", "Table", "Theorem", "Lemma", "Chapter"}
)


@cache
def _segmenter() -> pysbd.Segmenter:
    return pysbd.Segmenter(language="en", clean=False, char_span=True)


def _locate(text: str, sent: str, hint: int, cursor: int) -> int:
    """Start of ``sent`` in ``text``: pysbd's offset when it round-trips, else search."""
    if hint >= cursor and text[hint : hint + len(sent)] == sent:
        return hint
    return text.find(sent, cursor)


def _pysbd_spans(block: LogicalBlock) -> list[Span]:
    """pysbd's sentences as stripped, exact offsets into block.text."""
    text = block.text
    spans: list[Span] = []
    cursor = 0
    for span in _segmenter().segment(text):
        raw = span.sent
        sent = raw.strip()
        if not sent:
            continue
        hint = span.start + (len(raw) - len(raw.lstrip()))
        start = _locate(text, sent, hint, cursor)
        if start < 0 or text[start : start + len(sent)] != sent:
            raise ValueError(f"block {block.id}: sentence offsets do not round-trip: {sent!r}")
        cursor = start + len(sent)
        spans.append((start, cursor))
    return spans


def _starts_capital(text: str) -> bool:
    stripped = text.lstrip(_OPENERS)
    return bool(stripped) and stripped[0].isupper()


def _is_initial_end(tokens: list[str]) -> bool:
    """True when the last token is an initial that cannot end a sentence."""
    last = tokens[-1]
    if not _INITIAL.fullmatch(last):
        return False
    if last.startswith("(") or len(tokens) == 1:
        return True
    prev = tokens[-2]
    return bool(
        _INITIAL.fullmatch(prev.lstrip("("))
        or prev.endswith(",")
        or _REFERENCE_MARKER.fullmatch(prev)
    )


def _should_merge(prev: str, nxt: str, abbreviations: AbbreviationSet) -> bool:
    """True when the split between ``prev`` and ``nxt`` is not a sentence boundary."""
    if _SECTION_NUMBER.fullmatch(prev):
        return True
    if nxt[0] in ",;" or (nxt[0] in "-–" and len(nxt) > 1 and not nxt[1].isspace()):
        return True
    tokens = prev.split()
    token = tokens[-1].lstrip(_OPENERS).lower()
    if token in abbreviations.non_terminal:
        return True
    if token in ("www.", "http://www.", "https://www.") and _DOMAIN_START.match(nxt):
        # "my blog at www. ericpartaker.com": a line break inside a web address (ING-6).
        return True
    if token in abbreviations.before_number:
        # "No. [10] Our bodies" is a reference entry after a real sentence end, not "No. [3]".
        return (
            nxt[0].isdigit()
            or nxt[0] in "(#"
            or (nxt[0] == "[" and not _REFERENCE_ENTRY.match(nxt))
        )
    if token in abbreviations.may_end:
        return not _starts_capital(nxt)
    if _is_initial_end(tokens):
        return True
    if prev.rstrip(_TRAILING_CLOSERS)[-1:] in tuple(_TERMINAL):
        return False
    if nxt[0].islower() or nxt[0].isdigit():
        return True
    if nxt[0] != "(":
        return False
    # "(i)" after an unterminated span: a list item ("and (ii) when ...", "(b) Accuracy")
    # stays split; maths notation ("PA (i), CH (i)", "Fi (xi))") and an open bracket
    # ("(System 1) scans") are joined.
    if prev.count("(") > prev.count(")") or not _PLAIN_WORD.fullmatch(tokens[-1]):
        return True
    close = nxt.find(")")
    after = nxt[close + 1 :].lstrip() if close > 0 else ""
    return bool(after) and not after[0].isalpha()


def _has_word_char(text: str, prev_end: int, start: int, end: int) -> bool:
    """True when the token cut at ``start`` has word characters on both sides of the cut."""
    left = text[:prev_end].rsplit(None, 1)[-1] if text[:prev_end].strip() else ""
    right = text[start:end].split(None, 1)[0]
    return any(c.isalnum() for c in left) and any(c.isalnum() for c in right)


def _merge(text: str, spans: list[Span], abbreviations: AbbreviationSet) -> list[Span]:
    out: list[Span] = []
    for start, end in spans:
        if out:
            closers = _CLOSERS.match(text, start, end)
            if closers:
                out[-1] = (out[-1][0], closers.end())
                start = closers.end()
                while start < end and text[start].isspace():
                    start += 1
                if start >= end:
                    continue
            prev_start, prev_end = out[-1]
            # A pysbd split inside a token ("PA" | "(i)", "W." | "-Y.") is kept: the M1
            # golden (D14) counts those halves as two words, so joining them would change
            # the word-level score. A split before pure punctuation ("seq." | ", Public") is
            # not a word break and may be undone.
            joins_words = start == prev_end and _has_word_char(text, prev_end, start, end)
            # "habits\n2. Stabilized": a numbered list item on its own line stays split.
            list_item = "\n" in text[prev_end:start] and _NUMBERED_ITEM.match(text, start, end)
            if (
                not joins_words
                and not list_item
                and _should_merge(text[prev_start:prev_end], text[start:end], abbreviations)
            ):
                out[-1] = (prev_start, end)
                continue
        out.append((start, end))
    return out


def _letter_splits(text: str, spans: list[Span]) -> list[Span]:
    out: list[Span] = []
    for start, end in spans:
        piece = text[start:end]
        cut = 0
        if _REFERENCE_MARKER.match(piece):  # "[4] J. Zhou, ... and L. Hou": a name list
            out.append((start, end))
            continue
        for m in _LETTER_END.finditer(piece):
            prev = m.group("prev")
            if prev in ("and", "&") or not (
                _LETTER_PREV.fullmatch(prev) or prev in _LETTER_PREV_WORDS
            ):
                continue
            rest = piece[m.end() :].lstrip()
            if len(piece[cut : m.end()].split()) < 3 or len(rest.split()) < 2:
                continue
            out.append((start + cut, start + m.end()))
            cut = len(piece) - len(rest)
        out.append((start + cut, end))
    return out


def _line_spans(text: str) -> list[Span]:
    """One stripped span per non-empty line (ING-7 table rows and cues)."""
    spans: list[Span] = []
    pos = 0
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped:
            start = pos + line.index(stripped)
            spans.append((start, start + len(stripped)))
        pos += len(line) + 1
    return spans


def split_sentences(
    block: LogicalBlock,
    *,
    document_id: int,
    order_start: int,
    id_start: int,
    abbreviations: AbbreviationSet = DEFAULT_ABBREVIATIONS,
    profile: DocumentProfile = PROSE_DEFAULT,
) -> list[Segment]:
    """Split block.text into sentence Segments; text == block.text[char_start:char_end]."""
    text = block.text
    if not text.strip():
        return []
    if block.type in ("table", "equation"):
        spans = _line_spans(text)  # ING-7: cue and row lines are one segment each
    else:
        spans = _letter_splits(text, _merge(text, _pysbd_spans(block), abbreviations))
    segments: list[Segment] = []
    for i, (start, end) in enumerate(spans):
        sent = text[start:end]
        if sent != sent.strip() or not sent:
            raise ValueError(f"block {block.id}: sentence offsets do not round-trip: {sent!r}")
        normalized, char_map = normalize(sent, heading=block.type == "heading", profile=profile)
        segments.append(
            Segment(
                id=id_start + i,
                document_id=document_id,
                block_id=block.id,
                order=order_start + i,
                section_id=None,
                text=sent,
                normalized_text=normalized,
                char_start=start,
                char_end=end,
                char_map=char_map,
            )
        )
    return segments
