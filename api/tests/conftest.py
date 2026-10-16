"""Helpers to build synthetic pages for the ingestion stage tests (ING-2..ING-6).

Import them directly: ``from tests.conftest import make_block, make_page, make_span``.
"""

from __future__ import annotations

from collections.abc import Sequence

from hearnarro.ingestion.models import BBox, Block, BlockType, Line, Page, Span


def union(boxes: Sequence[BBox]) -> BBox:
    return BBox(
        min(b.x0 for b in boxes),
        min(b.y0 for b in boxes),
        max(b.x1 for b in boxes),
        max(b.y1 for b in boxes),
    )


def make_span(
    text: str,
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    size: float = 10.0,
    font: str = "Helvetica",
    bold: bool = False,
    superscript: bool = False,
) -> Span:
    return Span(
        text=text,
        bbox=BBox(x0, y0, x1, y1),
        font=font,
        size=size,
        bold=bold,
        superscript=superscript,
    )


def make_block(
    page: int,
    index: int,
    lines: Sequence[Sequence[Span]] | Sequence[str],
    *,
    x0: float = 72.0,
    y0: float = 72.0,
    width: float = 468.0,
    size: float = 10.0,
    font: str = "Helvetica",
    bold: bool = False,
    type: BlockType = "body",
) -> Block:
    """Build a Block. String lines become one span each, stacked from (x0, y0), each
    ``width`` wide and ``1.2 * size`` tall; span lines keep their own boxes. Bboxes of
    lines and the block are the union of their spans."""
    built: list[Line] = []
    for i, line in enumerate(lines):
        if isinstance(line, str):
            top = y0 + i * 1.2 * size
            spans = [make_span(line, x0, top, x0 + width, top + 1.2 * size, size, font, bold)]
        else:
            spans = list(line)
        built.append(Line(spans=spans, bbox=union([s.bbox for s in spans])))
    return Block(
        page=page,
        index=index,
        bbox=union([ln.bbox for ln in built]),
        lines=built,
        type=type,
    )


def make_page(
    number: int,
    blocks: list[Block],
    width: float = 612.0,
    height: float = 792.0,
    image_bboxes: Sequence[BBox] = (),
    table_bboxes: Sequence[BBox] = (),
    has_text_layer: bool = True,
    figure_bboxes: Sequence[BBox] = (),
) -> Page:
    return Page(
        number=number,
        width=width,
        height=height,
        blocks=blocks,
        image_bboxes=list(image_bboxes),
        table_bboxes=list(table_bboxes),
        has_text_layer=has_text_layer,
        figure_bboxes=list(figure_bboxes),
    )
