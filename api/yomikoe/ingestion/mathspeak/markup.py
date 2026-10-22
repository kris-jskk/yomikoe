"""The small markup of ``math_speech.jsonl`` turned into stage-1 span geometry (EVAL-10, MATH-1..4).

Shared by the EVAL-10 suite (``evals/suites/eval10_mathspeak.py``) and the mathspeak unit tests so
both see the same geometry. Unicode scripts (``x²``, ``xᵢ``) stay characters; ``^{...}`` becomes
a superscript span (smaller, raised, ``superscript=True``) and ``_{...}`` a subscript span
(smaller, lowered); a line break in an equation block stacks the lines (numerator over
denominator); in a body block ``$...$`` marks a maths-font run (CMMI10, italic), the rest is
Helvetica. An equation block is all maths font.
"""

from __future__ import annotations

import re
from typing import Any

from yomikoe.ingestion.mathspeak.structure import MathSpan, label_of

MATH_FONT = "CMMI10"
TEXT_FONT = "Helvetica"
SIZE = 10.0
SCRIPT_SIZE = 7.0
_MARKUP = re.compile(r"([_^])\{([^{}]*)\}")


def markup_runs(text: str, math: bool) -> list[tuple[str, str, float, bool, float]]:
    """(text, font, size, superscript, baseline shift) runs of one line piece."""
    font = MATH_FONT if math else TEXT_FONT
    out: list[tuple[str, str, float, bool, float]] = []
    pos = 0
    for m in _MARKUP.finditer(text):
        if m.start() > pos:
            out.append((text[pos : m.start()], font, SIZE, False, 0.0))
        sup = m.group(1) == "^"
        out.append((m.group(2), MATH_FONT, SCRIPT_SIZE, sup, -4.0 if sup else 3.0))
        pos = m.end()
    if pos < len(text):
        out.append((text[pos:], font, SIZE, False, 0.0))
    return out


def markup_blocks(raw: str, block: str) -> list[Any]:
    """One stage-1 ``Block`` of type ``block`` holding ``raw`` with span geometry (docstring)."""
    from yomikoe.ingestion.models import BBox, Block, Line, Span

    lines: list[Line] = []
    for i, row in enumerate(raw.split("\n")):
        top = 200.0 + 14.0 * i
        pieces: list[tuple[str, bool]] = (
            [(row, True)]
            if block == "equation"
            else [(p, k % 2 == 1) for k, p in enumerate(row.split("$")) if p]
        )
        spans: list[Span] = []
        x = 72.0
        for piece, math in pieces:
            for text, font, size, sup, shift in markup_runs(piece, math):
                width = 0.5 * size * len(text)
                box = BBox(x, top + shift, x + width, top + shift + size)
                spans.append(Span(text, box, font, size, italic=font == MATH_FONT, superscript=sup))
                x += width
        if spans:
            box = BBox(spans[0].bbox.x0, top, spans[-1].bbox.x1, top + 12.0)
            lines.append(Line(spans, box))
    box = BBox(
        min(ln.bbox.x0 for ln in lines),
        lines[0].bbox.y0,
        max(ln.bbox.x1 for ln in lines),
        lines[-1].bbox.y1,
    )
    return [Block(page=0, index=0, bbox=box, lines=lines, type=block)]  # type: ignore[arg-type]


def markup_segment(raw: str, block: str) -> tuple[str, list[MathSpan]]:
    """Segment text and its ``MathSpan``s for one pair, built from ``markup_blocks`` geometry:
    an equation block is one display span over the whole text (lines joined by a space, label
    from a trailing "(N)"); in a body block each run of maths-font spans is one inline span."""
    (blk,) = markup_blocks(raw, block)
    text = ""
    spans: list[MathSpan] = []
    for li, line in enumerate(blk.lines):
        if li:
            text += " "
        for sp in line.spans:
            start = len(text)
            text += sp.text
            if block == "equation":
                continue
            if sp.font == MATH_FONT:
                if spans and spans[-1].end == start:
                    spans[-1].end = len(text)
                    spans[-1].runs.append(sp)
                else:
                    spans.append(MathSpan(start, len(text), False, [sp]))
    if block == "equation":
        runs = [sp for line in blk.lines for sp in line.spans]
        spans = [MathSpan(0, len(text), True, runs, label_of(text))]
    return text, spans
