"""MATH-1, MATH-2 (spec §3c): English connectives and prose fragments inside a maths span.

User finding 2026-10-21, equation (2) of ``tables_04_markov_kernel.pdf``: "surely, bµT ⇀ π, or,
equivalently, ∫ f dbµT = ..." was spoken "the fraction surely, over, end fraction mu sub t pi,
o r, equivalently, ...". (A) a two-letter connective set in an upright text font ("or") is a word,
not two juxtaposed letters; the same letters in a maths italic font stay letters. (B) a text-font
prose run above the display's main row with nothing set under it (the tail of the sentence before
the display) is not a numerator, so it neither becomes "the fraction ... over ..." nor takes the
next run's hat accent as its denominator.
"""

from __future__ import annotations

from pathlib import Path

from yomikoe.ingestion.mathspeak import speak_span
from yomikoe.ingestion.mathspeak.structure import MathSpan
from yomikoe.ingestion.models import BBox, Span

SIZE = 9.96
SMALL = 6.97
FIXTURE = Path(__file__).parent / "fixtures" / "pdfs" / "tables_04_markov_kernel.pdf"


def _run(text: str, font: str, x0: float, y0: float, size: float = SIZE) -> Span:
    width = 0.5 * size * len(text)
    return Span(text, BBox(x0, y0, x0 + width, y0 + size), font, size, italic=False)


def _speak(runs: list[Span], display: bool = False) -> str:
    text = "".join(r.text for r in runs)
    spoken, _ = speak_span(MathSpan(0, len(text), display, runs, None), text)
    return spoken


def test_math1_upright_connective_or_is_a_word() -> None:
    runs = [
        _run("x → π, ", "CMMI10", 100.0, 300.0),
        _run("or, equivalently, ", "SFRM1000", 140.0, 300.0),
        _run("y = 1", "CMMI10", 230.0, 300.0),
    ]
    spoken = _speak(runs)
    assert "or, equivalently" in spoken, spoken
    assert "o r" not in spoken, spoken


def test_math1_upright_connective_in_between_maths_tokens() -> None:
    runs = [
        _run("x ", "CMMI10", 100.0, 300.0),
        _run("in ", "CMR10", 110.0, 300.0),
        _run("A", "CMMI10", 125.0, 300.0),
    ]
    spoken = _speak(runs)
    assert spoken == "x in a", spoken


def test_math1_italic_two_letters_stay_letters() -> None:
    assert _speak([_run("dx", "CMMI10", 100.0, 300.0)]) == "d x"
    assert _speak([_run("xy", "CMMI10", 100.0, 300.0)]) == "x y"
    # an italic "or" is two variables: the connective rule is for text fonts only
    assert _speak([_run("or", "CMMI10", 100.0, 300.0)]) == "o r"


def test_math2_prose_tail_above_display_is_not_a_numerator() -> None:
    # geometry of equation (2), tables_04_markov_kernel.pdf page text (results 1185)
    runs = [
        _run("surely, ", "SFRM1000", 82.8, 605.3),
        _run("b", "CMEX10", 150.3, 630.5),
        _run("µ", "CMMI10", 149.8, 626.5),
        _run("T ", "CMMI7", 155.8, 630.4, SMALL),
        _run("⇀ π, ", "CMMI10", 164.9, 626.5),
        _run("or, equivalently, ", "SFRM1000", 208.0, 626.5),
        _run("f ", "CMMI10", 308.4, 626.5),
        _run("= ", "CMR10", 336.3, 626.5),
        _run("1 ", "CMR10", 349.1, 619.7),
        _run("T ", "CMMI10", 348.0, 633.3),
    ]
    spoken = _speak(runs, display=True)
    assert "fraction surely" not in spoken, spoken
    assert spoken.startswith("surely, mu hat sub t"), spoken
    assert "mu hat sub t" in spoken, spoken
    assert "1 over t" in spoken, spoken  # the real fraction on the main row stays one


def test_math1_math2_markov_equation_2_end_to_end() -> None:
    from yomikoe.ingestion.pipeline import ingest

    result = ingest(FIXTURE)
    (seg,) = [s for s in result.segments if s.text.startswith("surely,")]
    spoken = seg.normalized_text
    assert "or, equivalently" in spoken, spoken
    assert "o r," not in spoken, spoken
    assert "the fraction surely" not in spoken, spoken
    assert "mu hat sub t" in spoken.split("or,")[0], spoken


def _eq(raw: str) -> str:
    from yomikoe.ingestion.mathspeak.markup import markup_segment

    text, (span,) = markup_segment(raw, "equation")
    spoken, _ = speak_span(span, text)
    return spoken


def test_math3_measure_of_a_differential_is_with_respect_to() -> None:
    # equation (4) of tables_04_markov_kernel.pdf: ∫ φ(x) µ(dx) − ∫ φ(x) ν(dx)
    assert _eq("∫ φ(x) µ(dx)") == "the integral of phi of x with respect to mu"
    assert _eq("∫ g(y) ν(dy)") == "the integral of g of y with respect to nu"
    assert _eq("∫ f(x) P(dx)") == "the integral of f of x with respect to p"
    assert _eq("∫ φ(x) µ(dx) − ∫ φ(x) ν(dx)") == (
        "the integral of phi of x with respect to mu minus the integral of phi of x with respect to nu"
    )


def test_math3_plain_differential_and_non_measure_unchanged() -> None:
    assert _eq("∫ f(x) dx") == "the integral of f of x d x"
    assert _eq("f(dx)") == "f of d x"  # no integral: an ordinary application
    assert _eq("µ(dx)") == "mu of d x"
