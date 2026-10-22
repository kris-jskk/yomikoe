"""Text-font maths found by content, and prose frames that are no table or figure (MATH-2,
ING-3, ING-4; m5 phase 3d: formula_06..10 of gate (b))."""

from __future__ import annotations

from yomikoe.ingestion.extract import LayoutChar, is_prose_region, is_text_box
from yomikoe.ingestion.merge import content_spans
from yomikoe.ingestion.models import BBox


def _spoken(text: str) -> list[str]:
    return [text[s.start : s.end] for s in content_spans(text)]


def test_math2_content_relation_in_text_font() -> None:
    # textbook line (formula_07): relations in an upright text font, no maths font
    assert _spoken("p + q = 1 and q = 1 – p hold.") == ["p + q = 1", "q = 1 – p"]
    assert _spoken("Suppose X ~ N(5, 6). This says") == ["X ~ N(5, 6)"]


def test_math2_content_dash_after_symbolic_operand_only() -> None:
    # formula_06: "x – mean" is a minus; a prose dash or a year range is not
    assert _spoken('the difference "x – mean" is called') == ["x –"]
    assert _spoken("we divide by n − 1, one less") == ["n − 1"]
    assert _spoken("The model – a new one – from 2015 – 2020") == []


def test_math2_content_glyphs_and_ocr_tokens() -> None:
    # Greek letters and OCR tokens with a relation inside ("x=17", "Z=")
    # a lone glyph is left to the reader (glyph_spans), so "10 μm" stays a unit (EVAL-10 symbol_35)
    assert _spoken("a good estimate of σ.") == []
    assert _spoken("Cells are 10 μm wide.") == []
    assert _spoken("Suppose x=17, then Z= follows; see http://a.b/?q=1") == ["x=17", "Z="]
    assert _spoken("The mean of X is μ = np.") == ["μ = np"]


def test_math2_content_spans_keep_words_out_and_respect_taken() -> None:
    assert _spoken("value = mean + (#ofSTDEVs)(standard deviation)") == ["="]
    text = "then x = 2 holds"
    taken = content_spans(text)
    assert content_spans(text, taken) == []


def _line(x0: float, y: float, text: str, gap_after: int | None = None) -> list[LayoutChar]:
    chars, x = [], x0
    for k, ch in enumerate(text):
        chars.append(LayoutChar(ch, BBox(x, y, x + 5, y + 10), "Times", 10.0, True, None))
        x += 5 + (30 if gap_after is not None and k == gap_after else 0)
    return chars


def test_ing3_prose_between_rules_is_no_table() -> None:
    region = BBox(0, 0, 400, 300)
    prose = [_line(0, 20 * k, "x" * 70) for k in range(5)]
    assert is_prose_region(region, prose)
    rows = [_line(0, 20 * k, "a" * 30, gap_after=10) for k in range(5)]
    assert not is_prose_region(region, rows)
    assert not is_prose_region(region, prose[:3])  # at most TABLE_PROSE_LINES_MAX prose lines


def test_ing3_framed_prose_box_is_no_table() -> None:
    page_width = 600.0
    box = BBox(70, 100, 520, 160)
    lines = [_line(80, 110, "Exercises"), _line(90, 130, "1. Calculate the limit")]
    assert is_text_box(box, lines, page_width)
    assert not is_text_box(BBox(70, 100, 200, 160), lines, page_width)  # narrow: a table cell
    cols = [_line(80, 110, "a" * 20, gap_after=5), _line(80, 130, "b" * 20, gap_after=5)]
    assert not is_text_box(box, cols, page_width)
