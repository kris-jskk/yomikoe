"""Stage 3, reading order (D2, D3, ING-4). Page width 612: columns at x 50-290 and 322-562."""

import pytest

from hearnarro.ingestion.models import Block
from hearnarro.ingestion.order import READ_TYPES, detect_columns, order_document, order_page
from tests.conftest import make_block, make_page


def col1(index: int, y0: float, type: str = "body", page: int = 0) -> Block:
    return make_block(page, index, [f"c1-{index}"], x0=50, width=240, y0=y0, type=type)


def col2(index: int, y0: float, type: str = "body", page: int = 0) -> Block:
    return make_block(page, index, [f"c2-{index}"], x0=322, width=240, y0=y0, type=type)


def full(index: int, y0: float, type: str = "heading", page: int = 0) -> Block:
    return make_block(page, index, [f"full-{index}"], x0=50, width=512, y0=y0, type=type)


def _indices(blocks: list[Block]) -> list[int]:
    return [b.index for b in blocks]


def test_ing4_read_types() -> None:
    assert READ_TYPES == {"body", "heading", "list", "caption", "equation", "table"}


def test_ing4_detect_columns_two_clusters() -> None:
    blocks = [col1(0, 100), col1(1, 200), col2(2, 100), col2(3, 200)]
    n, split = detect_columns(blocks, 612)
    assert n == 2
    assert split == pytest.approx((170 + 442) / 2)


def test_ing4_detect_columns_one_cluster() -> None:
    blocks = [col1(0, 100), col1(1, 200), col1(2, 300)]
    assert detect_columns(blocks, 612) == (1, None)
    assert detect_columns([], 612) == (1, None)


def test_ing4_detect_columns_small_gap_is_one_column() -> None:
    near = make_block(0, 1, ["x"], x0=80, width=240, y0=200)  # x_mid 200: gap 30 < 0.08*612
    assert detect_columns([col1(0, 100), near], 612) == (1, None)


def test_ing4_detect_columns_ignores_full_width_blocks() -> None:
    # A wide block's x_mid (306) would form a second cluster with col1 (170) if counted.
    blocks = [col1(0, 100), col1(1, 200), full(2, 300, type="body")]
    assert detect_columns(blocks, 612) == (1, None)


def test_ing4_order_page_two_columns_drops_furniture_footnote_last() -> None:
    blocks = [
        make_block(0, 0, ["Running head"], x0=50, width=512, y0=20, type="header"),
        col2(1, 300),
        col1(2, 300),
        col2(3, 100),
        col1(4, 100),
        make_block(0, 5, ["1 A footnote."], x0=50, width=240, y0=700, type="footnote"),
        col1(6, 200),
        col2(7, 200, type="caption"),
        make_block(0, 8, [""], x0=322, width=240, y0=500, type="image"),
        make_block(0, 9, ["12"], x0=300, width=12, y0=760, type="footer"),
    ]
    ordered = order_page(make_page(0, blocks))
    assert _indices(ordered) == [4, 6, 2, 3, 7, 1, 5]


def test_ing4_order_page_single_column_sorted_by_top() -> None:
    blocks = [full(0, 300, type="body"), full(1, 100, type="body"), full(2, 200, type="list")]
    assert _indices(order_page(make_page(0, blocks))) == [1, 2, 0]


def test_ing4_full_width_block_is_column_break() -> None:
    blocks = [
        col1(0, 100),  # col1-above
        col2(1, 100),  # col2-above
        full(2, 300),  # full-width heading
        col1(3, 400),  # col1-below
        col2(4, 400),  # col2-below
        col1(5, 500),
        col2(6, 500),
    ]
    ordered = order_page(make_page(0, list(reversed(blocks))))
    assert _indices(ordered) == [0, 1, 2, 3, 5, 4, 6]


def test_ing4_order_document_concatenates_pages() -> None:
    p0 = make_page(0, [full(0, 200, type="body", page=0), full(1, 100, type="body", page=0)])
    p1 = make_page(1, [full(0, 100, type="body", page=1)])
    ordered = order_document([p0, p1])
    assert [(b.page, b.index) for b in ordered] == [(0, 1), (0, 0), (1, 0)]


def test_ing4_detect_columns_needs_a_gutter_not_just_a_midpoint_gap() -> None:
    # Right-aligned cover lines: midpoints differ by > 8% of the width but every candidate
    # gutter is crossed by the wide author block, so this is one column.
    blocks = [
        make_block(
            0, 0, ["Scott Rose Oliver Borchert Advanced Network Division"], x0=305, width=238
        ),
        make_block(0, 1, ["Stu Mitchell"], x0=470, width=73, y0=300),
        make_block(0, 2, ["Department of Homeland Security"], x0=348, width=195, y0=400),
    ]
    assert detect_columns(blocks, 612) == (1, None)


def test_ing4_detect_columns_ignores_blocks_spanning_the_gutter() -> None:
    # A narrow figure label spanning both columns (below the full-width threshold) is a
    # break, not a reason to give up on two columns.
    span = make_block(0, 4, ["Figure legend spanning both columns"], x0=150, width=300, y0=50)
    blocks = [col1(0, 100), col1(1, 200), col2(2, 100), col2(3, 200), span]
    assert detect_columns(blocks, 612) == (2, pytest.approx(306))


def test_ing4_order_page_skips_empty_blocks() -> None:
    blocks = [col1(0, 100), make_block(0, 1, [" "], x0=50, width=20, y0=300)]
    assert _indices(order_page(make_page(0, blocks))) == [0]


def test_ing4_order_page_drops_noise() -> None:
    blocks = [col1(0, 100), make_block(0, 1, ["arXiv stamp"], x0=10, width=20, type="noise")]
    assert _indices(order_page(make_page(0, blocks))) == [0]
