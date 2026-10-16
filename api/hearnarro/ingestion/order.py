"""Stage 3: reading order, two-column detection (D2, D3, ING-4)."""

from __future__ import annotations

from hearnarro.ingestion.models import Block, Line, Page

READ_TYPES = {"body", "heading", "list", "caption", "equation", "table"}
GUTTER_FRAC = 0.015  # minimum gutter width, fraction of page width
CROSS_FRAC = 0.05  # at most this share of the text may straddle the gutter
NARROW_SHARE = 0.5  # narrow blocks must hold at least this share of the page's text
SIDE_FRAC = 0.10  # each column holds at least this share of the text
CROSS_SIDE_FRAC = 0.05  # a block reaching this far past a gutter on both sides costs nothing
BREAK_SIDE_FRAC = 9.0  # a block reaching this far past split_x on both sides is full-width
INLINE_HOSTS = {"body", "list"}  # prose lines; display equations keep extraction order
INLINE_TYPES = {"body", "equation", "list"}
INLINE_OVERLAP = 0.8  # vertical overlap, fraction of the shorter line, to share a text line
INLINE_BACK = 0.75  # a fragment may start this many font sizes left of the line's end
INLINE_GAP = 1.0  # ... and at most this many font sizes right of it
INLINE_LOOKAHEAD = 10  # fragments are searched among this many following blocks
INLINE_DROP = 0.4  # a fragment centred this many font sizes below the line hangs below it
INLINE_HOST_CHARS = 30  # a host is prose: at least this many non-space characters


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


def _text_lines(block: Block) -> list[Line]:
    return [ln for ln in block.lines if ln.text.strip()]


def _line_size(line: Line) -> float:
    return max((s.size for s in line.spans), default=0.0)


def _continues_line(y0: float, y1: float, x1: float, size: float, line: Line) -> bool:
    """``line`` sits on the text line spanning y0..y1 and starts right where it ends at x1."""
    overlap = min(y1, line.bbox.y1) - max(y0, line.bbox.y0)
    shorter = min(y1 - y0, line.bbox.height)
    if shorter <= 0 or overlap < INLINE_OVERLAP * shorter:
        return False
    if line.bbox.y_mid - (y0 + y1) / 2 > INLINE_DROP * size:
        return False  # hangs below the line: sum limits, fraction denominators stay put
    return x1 - INLINE_BACK * size <= line.bbox.x0 <= x1 + INLINE_GAP * size


def _is_prose(block: Block) -> bool:
    return block.type in INLINE_HOSTS and len("".join(block.text.split())) >= INLINE_HOST_CHARS


def _is_fragment_of(frag: Block, host: Block, y0: float, y1: float, x1: float, size: float) -> bool:
    flines = _text_lines(frag)
    return (
        frag.page == host.page
        and frag.type in INLINE_TYPES
        and not frag.inline
        and not _is_prose(frag)
        and len(flines) == 1
        and _continues_line(y0, y1, x1, size, flines[0])
    )


def attach_inline(blocks: list[Block]) -> list[Block]:
    """Pull inline maths fragments next to the prose line they continue (ING-4).

    PyMuPDF splits a line with inline maths into several blocks whose bboxes include sub-
    and superscripts, so sorting by top y can put a fragment before its host or after the
    next line. A host is a body/list block of at least INLINE_HOST_CHARS non-space chars
    (display-equation pieces are never hosts). A fragment is a body/equation/list block on
    the same page whose first text line overlaps the host's last text line vertically by
    >= INLINE_OVERLAP of the shorter line, is not centred more than INLINE_DROP font sizes
    below it (sum limits, fraction denominators), and starts within [-INLINE_BACK,
    +INLINE_GAP] font sizes of where that line ends. The leftmost fragment among the next
    INLINE_LOOKAHEAD blocks (or a one-line fragment sorted just before the host) is placed
    after the host, and the search repeats from the end of the fragment (a multi-line
    fragment's last line becomes the new line). Every fragment in the chain is marked
    ``inline`` and stage 4 joins it to the host's text, whether or not extraction order had
    split the chain (D12 rule 2). Display equations (own block, own line) never overlap a
    prose line, so they stay separate.
    """
    pool = list(blocks)
    out: list[Block] = []
    while pool:
        host = pool.pop(0)
        out.append(host)
        lines = _text_lines(host)
        if not _is_prose(host) or not lines:
            continue
        y0, y1 = lines[-1].bbox.y0, lines[-1].bbox.y1
        x1, size = lines[-1].bbox.x1, _line_size(lines[-1])
        chain: list[Block] = []
        if len(out) >= 2 and _is_fragment_of(out[-2], host, y0, y1, x1, size):
            chain.append(out.pop(-2))  # a fragment sorted just before its host (ties on top y)
            out.append(chain[-1])
            x1 = max(x1, _text_lines(chain[-1])[-1].bbox.x1)
        while True:
            cands = [
                b
                for b in pool[:INLINE_LOOKAHEAD]
                if b.page == host.page
                and b.type in INLINE_TYPES
                and _text_lines(b)
                and _continues_line(y0, y1, x1, size, _text_lines(b)[0])
            ]
            if not cands:
                break
            frag = min(cands, key=lambda b: _text_lines(b)[0].bbox.x0)
            pool.remove(frag)
            out.append(frag)
            chain.append(frag)
            flines = _text_lines(frag)
            if len(flines) > 1:
                y0, y1, x1 = flines[-1].bbox.y0, flines[-1].bbox.y1, flines[-1].bbox.x1
                size = _line_size(flines[-1])
            else:
                x1 = max(x1, flines[0].bbox.x1)
        for frag in chain:
            frag.inline = True  # D12 rule 2: joined in all cases
    return out


def order_page(
    page: Page, *, gap_frac: float = GUTTER_FRAC, full_width_frac: float = 0.60
) -> list[Block]:
    """Readable blocks of one page in reading order: lead blocks (stage 2's folded vertical
    titles) first by top y, then the columns, footnotes last."""
    readable = [b for b in page.blocks if b.type in READ_TYPES and b.text.strip()]
    leads = sorted((b for b in readable if b.lead), key=lambda b: b.bbox.y0)
    readable = [b for b in readable if not b.lead]
    footnotes = [b for b in page.blocks if b.type == "footnote"]
    _, split_x = detect_columns(
        readable, page.width, gap_frac=gap_frac, full_width_frac=full_width_frac
    )
    return (
        leads
        + attach_inline(_linearize(readable, split_x, page.width, full_width_frac))
        + _linearize(footnotes, split_x, page.width, full_width_frac)
    )


def order_document(pages: list[Page]) -> list[Block]:
    """Concatenation of order_page over pages."""
    return [b for page in pages for b in order_page(page)]
