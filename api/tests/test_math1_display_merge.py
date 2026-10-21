"""MATH-1, MATH-4: one display equation split by stage 1 into several blocks (its label "(13)",
a lone large-operator glyph, limits above and below it) reaches stage 4 as one equation block
with one display span and its label (``order.merge_display_pieces``, m5-p3f)."""

from __future__ import annotations

from yomikoe.ingestion.merge import merge_blocks
from yomikoe.ingestion.models import BBox, Block, Line, Page, Span
from yomikoe.ingestion.order import merge_display_pieces, order_page


def _block(
    index: int, text: str, x0: float, y0: float, x1: float, y1: float, **kw: object
) -> Block:
    size = float(kw.pop("size", 10.0))  # type: ignore[arg-type]
    box = BBox(x0, y0, x1, y1)
    span = Span(text, box, "CMMI10", size)
    return Block(page=0, index=index, bbox=box, lines=[Line([span], box)], **kw)  # type: ignore[arg-type]


def _eq(
    index: int, text: str, x0: float, y0: float, x1: float, y1: float, size: float = 10.0
) -> Block:
    return _block(index, text, x0, y0, x1, y1, type="equation", size=size)


def _sum_display() -> list[Block]:
    """formula_03 eq. 13 as stage 1 splits it: upper limit and sum sign, lower limit, body, label."""
    return [
        _eq(18, "TX", 287.7, 457.7, 302.1, 472.3),
        _eq(20, "Et−1∥dt∥2,", 303.8, 465.8, 348.4, 478.6),
        _eq(21, "(13)", 495.9, 467.8, 513.6, 477.7),
        _eq(17, "⟨M⟩T :=", 246.9, 467.8, 285.0, 478.6),
        _eq(19, "t=1", 288.4, 481.8, 301.5, 488.8, size=7.0),
    ]


def test_math1_split_display_becomes_one_block_left_to_right_top_to_bottom() -> None:
    out = merge_display_pieces(_sum_display())
    assert len(out) == 1
    block = out[0]
    assert block.type == "equation"
    assert [ln.text for ln in block.lines] == ["⟨M⟩T :=", "TX", "t=1", "Et−1∥dt∥2,", "(13)"]
    assert block.index == 17
    assert (block.bbox.x0, block.bbox.y0, block.bbox.x1, block.bbox.y1) == (
        246.9,
        457.7,
        513.6,
        488.8,
    )


def test_math1_math4_merged_display_has_one_span_and_its_label() -> None:
    logical = merge_blocks(merge_display_pieces(_sum_display()))
    assert len(logical) == 1
    lb = logical[0]
    assert lb.text == "⟨M⟩T := TX t=1 Et−1∥dt∥2, (13)"
    assert lb.raw_text == lb.text
    assert len(lb.math_spans) == 1
    span = lb.math_spans[0]
    assert span.display and (span.start, span.end) == (0, len(lb.text))
    assert span.label == "13"
    assert "".join(r.text for r in span.runs).replace(" ", "") == lb.text.replace(" ", "")


def test_math4_label_only_body_block_joins_the_equation_on_its_line() -> None:
    blocks = [
        _eq(1, "a = b + c,", 200.0, 100.0, 300.0, 112.0),
        _block(2, "(3)", 495.0, 101.0, 513.0, 111.0),  # stage 2 left the label as body
    ]
    out = merge_display_pieces(blocks)
    assert [b.text for b in out] == ["a = b + c,\n(3)"]
    assert out[0].type == "equation"
    assert merge_blocks(out)[0].math_spans[0].label == "3"


def test_math1_lone_operator_glyph_on_the_line_is_joined() -> None:
    blocks = [
        _eq(2, "Z", 252.8, 103.2, 258.3, 113.2),
        _eq(1, "(µP)(A) :=", 200.0, 112.7, 250.0, 122.7),
        _eq(3, "P(x, A) µ(dx), A ∈B(X).", 264.4, 112.7, 395.3, 123.0),
        _eq(4, "(10)", 496.0, 112.7, 513.7, 122.7),
    ]
    out = merge_display_pieces(blocks)
    assert [ln.text for ln in out[0].lines] == [
        "(µP)(A) :=",
        "Z",
        "P(x, A) µ(dx), A ∈B(X).",
        "(10)",
    ]


def test_math4_two_numbered_equations_stay_two_displays() -> None:
    blocks = [
        _eq(1, "a = b, (1)", 200.0, 100.0, 513.0, 112.0),
        _eq(2, "c = d. (2)", 200.0, 114.0, 513.0, 126.0),  # directly below, own label
    ]
    assert len(merge_display_pieces(blocks)) == 2


def test_math1_separate_displays_and_prose_pass_through() -> None:
    prose = _block(
        5, "The process is stationary if the chain starts at its law.", 82.0, 140.0, 512.0, 190.0
    )
    blocks = [
        _eq(1, "x = y", 250.0, 100.0, 300.0, 112.0),
        prose,
        _eq(6, "u = v", 250.0, 200.0, 300.0, 212.0),
    ]
    out = merge_display_pieces(blocks)
    assert out == blocks
    assert out[1] is prose


def test_math1_order_page_merges_before_reading_order() -> None:
    page = Page(number=0, width=595.0, height=842.0, blocks=_sum_display())
    ordered = order_page(page)
    assert len(ordered) == 1 and ordered[0].text.endswith("(13)")


def test_math1_body_left_hand_side_on_the_line_joins_and_keeps_reading_position() -> None:
    """academic_03 p.4: stage 2 typed "∆cyc =" body; the sum's upper limit sits above it, so a
    merged display without it would be read before its own left-hand side."""
    lhs = _block(34, "∆cyc =", 306.1, 634.5, 339.2, 646.5)
    blocks = [
        _block(
            33,
            "To measure whether a model prefers to repeat, we compute",
            306.1,
            451.6,
            524.4,
            611.6,
        ),
        lhs,
        _eq(35, "32\nX", 342.3, 623.2, 358.0, 639.5),
        _eq(36, "t=1", 343.2, 649.8, 357.1, 657.8, size=7.0),
        _eq(38, "log pθ(x | prefix)", 366.8, 630.1, 488.9, 647.7),
        _block(
            42, "where a larger ∆cyc indicates a stronger preference.", 306.1, 691.4, 524.4, 716.1
        ),
    ]
    out = merge_display_pieces(blocks)
    assert [b.index for b in out] == [33, 34, 42]
    assert out[1].type == "equation"
    assert out[1].lines[0].text == "∆cyc ="
    page = Page(number=0, width=595.0, height=842.0, blocks=blocks)
    assert [b.index for b in order_page(page)] == [33, 34, 42]


def test_math1_a_body_sentence_is_never_a_display_piece() -> None:
    blocks = [
        _block(1, "so that x =", 82.0, 100.0, 140.0, 112.0),  # short, but on no equation's line
        _eq(2, "a = b", 250.0, 300.0, 300.0, 312.0),
        _block(3, "The value we report is", 82.0, 301.0, 240.0, 311.0),  # no relation at its end
    ]
    assert merge_display_pieces(blocks) == blocks
