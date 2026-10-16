import pytest

from hearnarro.ingestion.models import BBox
from tests.conftest import make_block, make_span


def test_ing3_bbox_dimensions() -> None:
    b = BBox(10, 20, 110, 70)
    assert b.width == 100
    assert b.height == 50
    assert b.x_mid == 60
    assert b.y_mid == 45


@pytest.mark.parametrize(
    ("other", "expected"),
    [
        (BBox(50, 50, 150, 150), True),  # partial overlap
        (BBox(20, 20, 30, 30), True),  # contained
        (BBox(100, 0, 200, 100), False),  # touching edge only
        (BBox(200, 200, 300, 300), False),  # disjoint
        (BBox(0, 150, 100, 200), False),  # same column, below
    ],
)
def test_ing3_bbox_overlaps(other: BBox, expected: bool) -> None:
    box = BBox(0, 0, 100, 100)
    assert box.overlaps(other) is expected
    assert other.overlaps(box) is expected


def test_ing3_line_text_joins_spans() -> None:
    block = make_block(
        0,
        0,
        [[make_span("Hello ", 0, 0, 30, 12), make_span("world", 30, 0, 60, 12, bold=True)]],
    )
    assert block.lines[0].text == "Hello world"
    assert block.lines[0].bbox == BBox(0, 0, 60, 12)


def test_ing3_block_text_is_raw_newline_joined() -> None:
    block = make_block(0, 3, ["exam-", "ple text"])
    assert block.text == "exam-\nple text"
    assert block.index == 3
    assert block.type == "body"
    assert block.ocr is False
    assert block.bbox.y0 == 72.0
    assert block.bbox.y1 == pytest.approx(72.0 + 2 * 12.0)
