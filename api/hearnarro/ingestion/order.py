"""Stage 3: reading order, two-column detection (D2, D3, ING-4)."""

from __future__ import annotations

from hearnarro.ingestion.models import Block, Page

READ_TYPES = {"body", "heading", "list", "caption", "equation", "table"}


def detect_columns(
    blocks: list[Block],
    page_width: float,
    *,
    gap_frac: float = 0.08,
    full_width_frac: float = 0.60,
) -> tuple[int, float | None]:
    """Return (n_columns, split_x); split_x is None for one column.

    Blocks wider than ``full_width_frac * page_width`` are ignored. Two columns iff the
    largest gap between consecutive sorted x-midpoints exceeds ``gap_frac * page_width``.
    """
    mids = sorted(b.bbox.x_mid for b in blocks if b.bbox.width <= full_width_frac * page_width)
    if len(mids) < 2:
        return 1, None
    gap, i = max((mids[k + 1] - mids[k], k) for k in range(len(mids) - 1))
    if gap > gap_frac * page_width:
        return 2, (mids[i] + mids[i + 1]) / 2
    return 1, None


def _linearize(
    blocks: list[Block], split_x: float | None, page_width: float, full_width_frac: float
) -> list[Block]:
    """Column 1 then column 2 between full-width breaks; within a column, by top y."""
    if split_x is None:
        return sorted(blocks, key=lambda b: (b.bbox.y0, b.bbox.x0))
    breaks = sorted(
        (b for b in blocks if b.bbox.width > full_width_frac * page_width),
        key=lambda b: b.bbox.y0,
    )
    columnar = [b for b in blocks if b.bbox.width <= full_width_frac * page_width]
    out: list[Block] = []
    remaining = columnar
    for brk in [*breaks, None]:
        if brk is None:
            band, remaining = remaining, []
        else:
            band = [b for b in remaining if b.bbox.y0 < brk.bbox.y0]
            remaining = [b for b in remaining if b.bbox.y0 >= brk.bbox.y0]
        for left in (True, False):
            col = [b for b in band if (b.bbox.x_mid < split_x) == left]
            out.extend(sorted(col, key=lambda b: b.bbox.y0))
        if brk is not None:
            out.append(brk)
    return out


def order_page(page: Page, *, gap_frac: float = 0.08, full_width_frac: float = 0.60) -> list[Block]:
    """Readable blocks of one page in reading order, footnotes last."""
    readable = [b for b in page.blocks if b.type in READ_TYPES]
    footnotes = [b for b in page.blocks if b.type == "footnote"]
    _, split_x = detect_columns(
        readable, page.width, gap_frac=gap_frac, full_width_frac=full_width_frac
    )
    return _linearize(readable, split_x, page.width, full_width_frac) + _linearize(
        footnotes, split_x, page.width, full_width_frac
    )


def order_document(pages: list[Page]) -> list[Block]:
    """Concatenation of order_page over pages."""
    return [b for page in pages for b in order_page(page)]
