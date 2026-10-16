"""Stage 3: reading order, two-column detection (D2, D3, ING-4)."""

from __future__ import annotations

from hearnarro.ingestion.models import Block, Page

READ_TYPES = {"body", "heading", "list", "caption", "equation", "table"}
GUTTER_FRAC = 0.015  # minimum gutter width, fraction of page width
CROSS_FRAC = 0.05  # at most this share of the text may straddle the gutter
NARROW_SHARE = 0.5  # narrow blocks must hold at least this share of the page's text
SIDE_FRAC = 0.10  # each column holds at least this share of the text
CROSS_SIDE_FRAC = 0.05  # a block reaching this far past a gutter on both sides costs nothing
BREAK_SIDE_FRAC = 9.0  # a block reaching this far past split_x on both sides is full-width


def _weight(block: Block) -> int:
    return max(1, len(block.text.strip()))


def detect_columns(
    blocks: list[Block],
    page_width: float,
    *,
    gap_frac: float = GUTTER_FRAC,
    full_width_frac: float = 0.60,
) -> tuple[int, float | None]:
    """Return (n_columns, split_x); split_x is None for one column.

    Blocks wider than ``full_width_frac * page_width`` are ignored. Every x in the middle
    half of the page is a candidate gutter; its cost is the text (chars) of blocks that
    straddle it by less than CROSS_SIDE_FRAC on one side (blocks reaching further on both
    sides are full-width breaks and cost nothing). Two columns iff the cheapest run of candidates is at least
    ``gap_frac * page_width`` wide, straddled by at most CROSS_FRAC of the text, and has at
    least SIDE_FRAC of the text on each side, and narrow blocks hold at least NARROW_SHARE
    of all the text. split_x is the centre of that run.
    """
    narrow = [b for b in blocks if b.bbox.width <= full_width_frac * page_width]
    if len(narrow) < 2:
        return 1, None
    total = sum(_weight(b) for b in narrow)
    if total < NARROW_SHARE * sum(_weight(b) for b in blocks):
        return 1, None  # mostly full-width text: one column with inline fragments
    lo, hi = int(page_width * 0.25), int(page_width * 0.75)
    reach = CROSS_SIDE_FRAC * page_width
    costs: list[tuple[int, int, int]] = []  # (x, crossing, min(left, right))
    for x in range(lo, hi + 1):
        crossing = left = right = 0
        for b in narrow:
            if b.bbox.x1 <= x:
                left += _weight(b)
            elif b.bbox.x0 >= x:
                right += _weight(b)
            elif b.bbox.x0 >= x - reach or b.bbox.x1 <= x + reach:
                crossing += _weight(b)  # spanning blocks are breaks, not crossings
        costs.append((x, crossing, min(left, right)))
    ok = [(x, c) for x, c, side in costs if c <= CROSS_FRAC * total and side >= SIDE_FRAC * total]
    if not ok:
        return 1, None
    runs: list[tuple[int, list[int]]] = []  # (cost, contiguous xs with that cost)
    for x, c in ok:
        if runs and runs[-1][0] == c and x == runs[-1][1][-1] + 1:
            runs[-1][1].append(x)
        else:
            runs.append((c, [x]))
    wide = [(c, xs) for c, xs in runs if len(xs) >= gap_frac * page_width]
    if not wide:
        return 1, None
    _, run = min(wide, key=lambda r: (r[0], -len(r[1])))
    return 2, (run[0] + run[-1]) / 2


def _is_break(block: Block, split_x: float, page_width: float, full_width_frac: float) -> bool:
    """Full-width: wider than full_width_frac, or straddling split_x by CROSS_SIDE_FRAC each way."""
    if block.bbox.width > full_width_frac * page_width:
        return True
    reach = BREAK_SIDE_FRAC * page_width
    return block.bbox.x0 < split_x - reach and block.bbox.x1 > split_x + reach


def _linearize(
    blocks: list[Block], split_x: float | None, page_width: float, full_width_frac: float
) -> list[Block]:
    """Column 1 then column 2 between full-width breaks; within a column, by top y."""
    if split_x is None:
        return sorted(blocks, key=lambda b: (b.bbox.y0, b.bbox.x0))
    breaks = sorted(
        (b for b in blocks if _is_break(b, split_x, page_width, full_width_frac)),
        key=lambda b: b.bbox.y0,
    )
    columnar = [b for b in blocks if not _is_break(b, split_x, page_width, full_width_frac)]
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


def order_page(
    page: Page, *, gap_frac: float = GUTTER_FRAC, full_width_frac: float = 0.60
) -> list[Block]:
    """Readable blocks of one page in reading order, footnotes last."""
    readable = [b for b in page.blocks if b.type in READ_TYPES and b.text.strip()]
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
