"""MATH-1..4, gate (b): partial parse, scripts as words, CMEX accents and underbraces, three-level
displays, set-builder and function wording on span geometry shaped like the text-layer papers."""

from __future__ import annotations

from hearnarro.ingestion.mathspeak import coalesce_spans, speak_segment, speak_span
from hearnarro.ingestion.mathspeak.reader import speak
from hearnarro.ingestion.mathspeak.structure import MathSpan, parse
from hearnarro.ingestion.models import BBox, Span


def run(text: str, x: float, y: float, size: float = 10.0, font: str = "CMMI10") -> Span:
    """A run whose top is ``y``; scripts are smaller and shifted like TeX sets them."""
    return Span(text, BBox(x, y, x + 5 * len(text), y + size), font, size)


def said(runs: list[Span], display: bool = True, label: str | None = None) -> str:
    text = "".join(r.text for r in runs)
    return speak_span(MathSpan(0, len(text), display, runs, label), text)[0]


def test_math1_partial_parse_speaks_the_structured_parts() -> None:
    # an unclosed bracket (its closer is on the next line) and an unknown glyph
    runs = [run("x", 0, 0), run("i", 5, 4, 7.0), run(" = f(a + ☃", 10, 0)]
    span = MathSpan(0, 12, True, runs, "4")
    assert parse(span) is None
    node = parse(span, partial=True)
    assert node is not None
    assert speak(node) == "x sub i equals f of a plus"
    assert said(runs, label="4") == "equation 4: x sub i equals f of a plus"


def test_math1_partial_parse_keeps_char_map_rule() -> None:
    text = "y = (a + b (2)"
    runs = [run(text, 0, 0)]
    out, cmap = speak_segment(text, [MathSpan(0, len(text), True, runs, "2")])
    assert out.startswith("equation 2: y equals a plus b")
    assert len(cmap) == len(out) and cmap == sorted(cmap) and max(cmap) < len(text)


def test_math2_multi_letter_scripts_read_as_words() -> None:
    runs = [run("E", 0, 0, font="CMSY10"), run("marg", 6, 4, 7.0, "CMR7")]
    assert said(runs, display=False) == "e sub marg"
    runs = [run("L", 0, 0, font="CMSY10"), run("Stage I", 6, 4, 8.0, "CMR8")]
    assert said(runs, display=False) == "l sub stage i"
    runs = [run("L", 0, 0, font="CMSY10"), run("wCE", 6, 4, 8.0, "CMR8")]
    assert said(runs, display=False) == "l sub w c e"  # mixed case stays letters
    runs = [run("a = ", 0, 0), run("Update", 20, 0, font="TeXGyreTermes")]
    assert said(runs, display=False) == "a equals update"


def test_math2_cmex_accents_and_primes_as_scripts() -> None:
    hat = [run("b", 0, 1, font="CMEX10"), run("Z", 1, 0), run("comp", 6, 4, 7.0, "CMR7")]
    assert said(hat, display=False) == "z hat sub comp"
    prime = [run("R", 0, 0), run("Π", 6, 4, 7.0, "CMR7"), run("′", 11, 3.5, 5.0, "CMSY5")]
    prime += [run("(q)", 14, 0, font="CMR10")]
    assert said(prime, display=False) == "r sub capital pi prime of q"


def test_math2_nested_and_split_scripts() -> None:
    # m_t then +1 in a second run is one subscript; K_2 inside an exponent is a nested sub
    assert said([run("m", 0, 0), run("t", 6, 4, 8.0), run("+1", 9, 4, 8.0, "CMR8")]) == (
        "m sub t plus 1"
    )
    runs = [run("n", 0, 0), run("K", 6, -3, 7.0), run("2", 10, 0, 5.0, "CMR5")]
    assert said(runs, display=False) == "n to the k sub 2"
    tensor = [run("p", 0, 0), run("⊗", 6, -3, 7.0, "CMSY7"), run("n", 11, -3, 7.0)]
    assert said(tensor, display=False) == "p to the tensor power n"


def test_math2_underbrace_label_and_stacked_half() -> None:
    runs = [
        run("C", 0, 0),
        run("1 ", 6, 4, 7.0, "CMR7"),
        run("= ", 10, 0, font="CMR10"),
        Span("1 ", BBox(20, -2, 24, 5), "CMR7", 7.0, superscript=True),
        run("2 ", 20, 6, 7.0, "CMR7"),
        run("x", 26, 0),
        run("| {z }", 26, 11, font="CMEX10"),
        run("rank", 26, 19, 7.0, "CMTI7"),
    ]
    assert said(runs) == "c sub 1 equals 1 half x, rank"


def test_math2_three_level_display_is_a_fraction_in_the_row() -> None:
    runs = [
        run("α = ", 0, 10),
        run("a + b", 30, 2),  # numerator above the maths axis
        run("c", 35, 18),  # denominator below it
        run(" + 1", 60, 10),
    ]
    assert said(runs) == "alpha equals the fraction a plus b over c, end fraction plus 1"


def test_math2_continued_display_is_not_a_fraction() -> None:
    first = [run("y = a", 40, 0)]
    second = [run("= b", 30, 16)]  # starts left of the numerator: an aligned second line
    assert said(first + second) == "y equals a equals b"
    stacked = [run("y = ", 0, 0), run("a", 20, 0), run("c", 20, 14)]
    assert said(stacked) == "y equals a over c"


def test_math2_set_builder_family_and_function_application() -> None:
    fam = [
        run("{(x", 0, 0, font="CMR10"),
        run("i", 12, 4, 7.0),
        run(", y", 15, 0),
        run("i", 24, 4, 7.0),
        run(")}", 27, 0, font="CMR10"),
        run("n", 36, -3, 7.0),
        run("i=1", 36, 5, 7.0),
    ]
    assert said(fam, display=False) == "the set of x sub i, y sub i for i equals 1 to n"
    family = [run("(X", 0, 0, font="CMR10"), run("t", 12, 4, 7.0), run(")", 15, 0, font="CMR10")]
    family.append(run("t≥0", 18, 4, 7.0))
    assert said(family, display=False) == "x sub t for t greater than or equal to 0"
    assert said([run("d(log N)", 0, 0)], display=False) == "d times log n"
    sb = [run("{f : X → R : f(x) = 0}", 0, 0)]
    assert said(sb, display=False) == "the set of f from x to r such that f of x equals 0"


def test_math2_inline_spans_split_by_font_are_joined() -> None:
    # "conditional p(y | x), and": p and "y | x" are math-font spans, "(" and "x)" are not
    text = "conditional p(y | x), and"
    s1 = MathSpan(12, 13, False, [run("p", 0, 0)])
    s2 = MathSpan(14, 18, False, [run("y | ", 10, 0)])
    (joined,) = coalesce_spans(text, [s1, s2])
    assert text[joined.start : joined.end] == "p(y | x)"
    assert speak_segment(text, [joined])[0] == "conditional p of y given x, and"
    # a prose word between two spans is never absorbed
    text = "a law p over (X"
    a, b = MathSpan(6, 7, False, [run("p", 0, 0)]), MathSpan(14, 15, False, [run("X", 9, 0)])
    assert len(coalesce_spans(text, [a, b])) == 2


def test_math3_text_font_minus_macron_and_power() -> None:
    # p3d-detection hands over text-font maths: en dash minus, macron after the letter, y**2
    assert said([run("x – μ", 0, 0, font="Helvetica")], display=False) == "x minus mu"
    assert said([run("x¯", 0, 0, font="Helvetica")], display=False) == "x bar"
    assert said([run("y**2", 0, 0, font="Helvetica")], display=False) == "y squared"
    from hearnarro.ingestion.mathspeak.symbols import name_of

    assert name_of("") is None and name_of("update") is None
    assert name_of(":=") == "is defined as"
