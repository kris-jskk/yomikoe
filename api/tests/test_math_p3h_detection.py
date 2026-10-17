"""Detection-side rules for display and inline maths that stage 2 typed as prose (MATH-1, MATH-2,
ING-3; m5 p3h, gate (b) formula_03, 05, 06, 09): text-font displays alone on their line,
one-line text rows of a display, a display's left half at the end of a body block, function
names and scientific notation inside prose."""

from __future__ import annotations

from hearnarro.ingestion.classify import _retype_text_displays
from hearnarro.ingestion.merge import content_spans, merge_blocks
from hearnarro.ingestion.models import BBox, Block, Line, Page, Span
from hearnarro.ingestion.order import merge_display_pieces


def _span(text: str, x0: float, y0: float, x1: float, y1: float, font: str = "CMMI10") -> Span:
    return Span(text, BBox(x0, y0, x1, y1), font, 10.0)


def _block(index: int, spans: list[Span], type_: str = "body") -> Block:
    box = BBox(
        min(s.bbox.x0 for s in spans),
        min(s.bbox.y0 for s in spans),
        max(s.bbox.x1 for s in spans),
        max(s.bbox.y1 for s in spans),
    )
    return Block(page=0, index=index, bbox=box, lines=[Line(spans, box)], type=type_)  # type: ignore[arg-type]


def _page(blocks: list[Block]) -> Page:
    return Page(number=3, width=612, height=792, blocks=blocks)


def _spoken(text: str) -> list[str]:
    return [text[s.start : s.end] for s in content_spans(text)]


# ---- claim 1: text-font displays -------------------------------------------------------------


def test_math1_text_font_display_alone_on_its_line_is_an_equation() -> None:
    # formula_07: "p + q = 1" on its own line, upright text font, no maths font
    alone = _block(2, [_span("p + q = 1", 72, 91, 106, 101, "LiberationSerif")])
    labelled = _block(3, [_span("x = µ + kσ (4)", 200, 120, 300, 130, "LiberationSerif")])
    _retype_text_displays(_page([alone, labelled]))
    assert alone.type == "equation"
    assert labelled.type == "equation"


def test_ing3_prose_and_maths_sharing_a_prose_line_stay_body() -> None:
    sentence = _block(0, [_span("p = the probability of a success for any trial", 72, 59, 237, 69)])
    prose = _block(
        1, [_span("The standard deviation is σ = 1 – p over p", 72, 327, 219, 352, "Liberation")]
    )
    tail = _block(2, [_span("= 1p − 1 .", 224, 330, 282, 347, "Liberation")])
    _retype_text_displays(_page([sentence, prose, tail]))
    assert [b.type for b in (sentence, prose, tail)] == ["body", "body", "body"]


# ---- claim 1: one-line text rows of a display (formula_05 eq. 2) -----------------------------


def test_math1_text_row_under_an_equation_joins_the_display() -> None:
    row1 = _block(1, [_span("at,i ∼πsel ϕ (· | q, ci, mt) ,", 125, 93, 235, 108)], "equation")
    row2 = _block(
        2,
        [
            _span("at,i ∈{", 125, 113, 150, 125),
            _span("Skip, Update", 150, 113, 222, 125, "TeXGyreTermes"),
            _span("}.", 222, 113, 226, 125),
        ],
    )
    label = _block(3, [_span("(2)", 277, 104, 290, 115, "NimbusRomNo9L")], "equation")
    out = merge_display_pieces([row1, row2, label])
    assert len(out) == 1 and out[0].type == "equation"
    lb = merge_blocks(out)[0]
    assert [sp.label for sp in lb.math_spans] == ["2"]
    assert "Skip, Update" in lb.text


def test_math1_a_prose_sentence_is_never_a_text_row() -> None:
    eq = _block(1, [_span("x = y", 125, 93, 160, 108)], "equation")
    prose = _block(2, [_span("where x is the input and y the output.", 125, 112, 300, 124)])
    out = merge_display_pieces([eq, prose])
    assert [b.type for b in out] == ["equation", "body"]


# ---- claim 2: a display's left half at the end of a body block (formula_03 eq. 11) -----------


def test_math1_display_tail_in_a_body_block_goes_to_the_display() -> None:
    first = Line(
        [
            _span(
                "The process is called stationary. We use the notation for",
                82,
                140,
                513,
                152,
                "SFRM1000",
            )
        ],
        BBox(82, 140, 513, 152),
    )
    tail_spans = [
        _span("n ", 83, 160, 90, 170),
        _span("≥", 90, 160, 97, 170, "CMSY10"),
        _span("0", 97, 160, 102, 170, "CMR10"),
        _span(". Recall that for a fixed ", 102, 160, 210, 170, "SFRM1000"),
        _span("T > ", 210, 160, 228, 170),
        _span("0", 228, 160, 233, 170, "CMR10"),
        _span(", ", 233, 160, 238, 170, "SFRM1000"),
        _span("bµT ", 250, 170, 268, 182),
        _span(":= 1 T T −1", 268, 154, 300, 192, "CMR10"),
    ]
    second = Line(tail_spans, BBox(83, 154, 317, 192))
    sigma = Line([_span("X", 302, 170, 316, 180, "CMEX10")], BBox(302, 170, 316, 180))
    body = Block(page=0, index=5, bbox=BBox(82, 140, 513, 192), lines=[first, second, sigma])
    lower = _block(6, [_span("t=0", 303, 189, 316, 196, "CMMI7")], "equation")
    term = _block(7, [_span("δXt", 319, 175, 333, 187)], "equation")
    label = _block(8, [_span("(11)", 496, 175, 514, 185, "SFRM1000")], "equation")
    out = merge_display_pieces([body, lower, term, label])
    assert [b.type for b in out] == ["body", "equation"]
    assert out[0].text.endswith("Recall that for a fixed T > 0, ")
    assert out[1].text.split("\n")[0] == "bµT := 1 T T −1"
    assert "X" in out[1].text and "t=0" in out[1].text and "δXt" in out[1].text
    logical = merge_blocks(out)
    assert [sp.label for sp in logical[-1].math_spans] == ["11"]


def test_math1_body_line_without_a_display_on_it_is_not_split() -> None:
    body = _block(0, [_span("for a fixed T > 0, we let µ := 1", 83, 160, 300, 170)])
    elsewhere = _block(1, [_span("x = y", 200, 300, 240, 310)], "equation")
    out = merge_display_pieces([body, elsewhere])
    assert [b.text for b in out] == [body.text, elsewhere.text]


# ---- claim 3: function names and scientific notation in prose (formula_09) -------------------


def test_math2_function_names_before_a_bracket_are_maths() -> None:
    text = "Consider the function exp(-1/(.1*x**2 + y**2). This function admits a minimum."
    assert _spoken(text) == ["exp(-1/(.1*x**2 + y**2)"]
    assert _spoken("it takes log(n) steps") == ["log(n)"]
    assert _spoken("the value of sin(x) + 1") == ["sin(x) + 1"]


def test_math2_function_names_inside_words_stay_prose() -> None:
    assert _spoken("we explain the maximum and the logistic model, then minimise it") == []
    assert _spoken("an expert (see the tanker) in the cost") == []


def test_math2_scientific_notation_is_maths_ranges_are_not() -> None:
    assert _spoken("try to get within 1e-8 of this minimum point.") == ["1e-8"]
    assert _spoken("a tolerance of 2.5E+3 or 10^-8 or 10−8") == ["2.5E+3", "10^-8", "10−8"]
    assert _spoken("see pages 10-8 and the years 1990-2000") == []
