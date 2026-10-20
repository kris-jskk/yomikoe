"""M5 phase 3 loop 8: fixture 09 (unicode-math display of a damped oscillator ODE): dot and
double-dot accents set as spacing glyphs before their letter, a display that opens with a stacked
fraction, a one-column stack in tall brackets read as a column vector (a several-column stack
keeps the matrix row), and one font on two levels split into two spans (MATH-1..3, gate b)."""

from __future__ import annotations

from hearnarro.ingestion.extract import _level_jump
from hearnarro.ingestion.mathspeak import reader, structure
from hearnarro.ingestion.mathspeak.structure import MathSpan
from hearnarro.ingestion.merge import _inline_spans
from hearnarro.ingestion.models import BBox, Line, Span

MI, MI7, RM, RM5, EX = (
    "LMMathItalic10-Regular",
    "LMMathItalic7-Regular",
    "LMRoman10-Regular",
    "LMRoman5-Regular",
    "LMMathExtension10-Regular",
)


def _run(text: str, x0: float, top: float, font: str = MI, size: float = 10.0) -> Span:
    return Span(text, BBox(x0, top, x0 + 5.0 * len(text), top + size), font, size)


def _say(runs: list[Span]) -> str:
    text = "".join(r.text for r in runs)
    node = structure.parse(MathSpan(0, len(text), True, runs), text)
    assert node is not None
    return " ".join(reader.speak(node).split())


def test_spacing_dot_accents_read_after_their_letter_math_1() -> None:
    for text, said in (("˙𝑦", "y dot"), ("¨𝑦", "y double dot"), ("𝑑˙𝑦", "d y dot")):
        node = structure.parse(MathSpan(0, len(text), False, []), text)
        assert node is not None
        assert " ".join(reader.speak(node).split()) == said


def test_display_opening_with_a_fraction_reads_it_math_3() -> None:
    # fixture 09 display 1: dy/dt = ẏ, the numerator is the first run
    runs = [
        _run("𝑑𝑦", 225.9, 303.3),
        _run("𝑑𝑡 ", 226.7, 316.9),
        _run("= ˙", 240.3, 310.1, RM),
        _run("𝑦", 250.8, 310.1),
    ]
    assert _say(runs) == "the fraction d y over d t, end fraction equals y dot"


def test_one_column_stack_in_tall_brackets_is_a_column_vector_math_3() -> None:
    # fixture 09 display 2, right side: = [z1; −(z1)] set with "[︂" and "]︂"
    runs = [
        _run("𝑤", 230.0, 361.5),
        _run("=", 237.0, 361.5, RM),
        _run("[︂ ", 247.5, 351.5, EX),
        _run("𝑧", 262.0, 355.4),
        _run("1", 267.0, 359.3, RM5, 7.0),
        _run("−", 252.0, 367.4, RM),
        _run("𝑧", 258.0, 367.4),
        _run("]︂", 280.0, 351.5, EX),
    ]
    assert _say(runs) == "w equals the column vector z sub 1, minus z"


def test_script_size_pairs_in_a_stack_are_fractions_math_3() -> None:
    # fixture 09 display 2, middle: [dz0/dt; dz1/dt], each entry a text-style fraction
    runs = [
        _run("𝑤", 230.0, 361.5),
        _run("=", 237.0, 361.5, RM),
        _run("[︂ ", 247.5, 351.5, EX),
        _run("𝑑𝑧", 254.0, 353.7, MI7, 6.97),
        _run("0", 261.9, 356.3, RM5, 4.98),
        _run("𝑑𝑡", 256.3, 361.3, MI7, 6.97),
        _run("𝑑𝑧", 254.0, 366.3, MI7, 6.97),
        _run("1", 261.9, 368.9, RM5, 4.98),
        _run("𝑑𝑡", 256.3, 373.8, MI7, 6.97),
        _run("]︂", 267.0, 351.5, EX),
    ]
    assert _say(runs) == (
        "w equals the column vector the fraction d z sub 0 over d t, end fraction,"
        " the fraction d z sub 1 over d t, end fraction"
    )


def test_several_column_stack_keeps_the_matrix_row_math_3() -> None:
    runs = [
        _run("𝑤", 230.0, 361.5),
        _run("=", 237.0, 361.5, RM),
        _run("[︂ ", 247.5, 351.5, EX),
        _run("𝑎", 255.0, 355.4),
        _run("𝑏", 280.0, 355.4),
        _run("𝑐", 255.0, 367.4),
        _run("𝑑", 280.0, 367.4),
        _run("]︂", 292.0, 351.5, EX),
    ]
    assert _say(runs) == "w equals the matrix with rows: a, b; c, d"


def test_one_font_on_two_levels_is_two_spans_math_1() -> None:
    row, num = BBox(250.8, 310.1, 255.7, 320.0), BBox(257.0, 303.3, 262.4, 313.3)
    assert _level_jump(row, num, 9.96)
    assert not _level_jump(row, BBox(256.0, 310.1, 261.0, 320.0), 9.96)  # same baseline
    assert not _level_jump(row, BBox(256.0, 306.0, 260.0, 320.0), 9.96)  # a taller glyph


def test_inline_spacing_accent_opens_the_maths_span_math_2() -> None:
    spans = [_run("computes ˙", 100.0, 100.0, RM), _run("𝑧", 150.0, 100.0)]
    line = Line(spans=spans, bbox=BBox(100.0, 100.0, 155.0, 110.0), dir=(1.0, 0.0))
    (sp,) = _inline_spans([line], [line.text], False)
    assert line.text[sp.start : sp.end] == "˙𝑧"
    assert [r.text for r in sp.runs] == ["˙", "𝑧"]
