"""M5 phase 3 loop 9: Leibniz derivatives read "d y over d t" with no fraction wrapper, stacked or
slashed, first order, second order and partial (spec §3c "Leibniz derivative"), a stacked fraction
of any other shape keeps "the fraction ..., end fraction", and a sign set in the text font with
its number between two inline maths runs ("¨y" "+2" "ζω0") joins the formula (MATH-1, MATH-3,
gate b)."""

from __future__ import annotations

from hearnarro.ingestion import mathspeak as ms
from hearnarro.ingestion.mathspeak import reader, structure
from hearnarro.ingestion.mathspeak.structure import MathSpan
from hearnarro.ingestion.models import BBox, Span

MI, RM, RM7 = "LMMathItalic10-Regular", "LMRoman10-Regular", "LMRoman7-Regular"


def _run(text: str, x0: float, top: float, font: str = MI, size: float = 10.0) -> Span:
    return Span(text, BBox(x0, top, x0 + 5.0 * len(text), top + size), font, size)


def _stacked(num: list[Span], den: list[Span]) -> str:
    runs = [*num, *den, _run("=", 250.0, 310.1, RM), _run("𝑓", 258.0, 310.1)]
    text = "".join(r.text for r in runs)
    node = structure.parse(MathSpan(0, len(text), True, runs), text)
    assert node is not None
    return " ".join(reader.speak(node).split())


def _inline(text: str) -> str:
    node = structure.parse(MathSpan(0, len(text), False, []), text)
    assert node is not None
    return " ".join(reader.speak(node).split())


def test_stacked_first_order_derivative_has_no_wrapper_math_3() -> None:
    said = _stacked([_run("𝑑𝑦", 225.9, 303.3)], [_run("𝑑𝑡", 226.7, 316.9)])
    assert said == "d y over d t equals f"


def test_stacked_second_order_derivative_math_3() -> None:
    num = [_run("𝑑", 225.9, 303.3), _run("2", 231.0, 301.0, RM7, 7.0), _run("𝑦", 235.0, 303.3)]
    den = [_run("𝑑𝑡", 225.9, 316.9), _run("2", 236.0, 314.6, RM7, 7.0)]
    assert _stacked(num, den) == "d squared y over d t squared equals f"


def test_stacked_partial_derivative_math_3() -> None:
    said = _stacked([_run("∂𝑦", 225.9, 303.3)], [_run("∂𝑡", 226.7, 316.9)])
    assert said == "partial y over partial t equals f"


def test_slashed_derivatives_math_3() -> None:
    assert _inline("𝑑𝑦/𝑑𝑡") == "d y over d t"
    assert _inline("𝑑²𝑦/𝑑𝑡²") == "d squared y over d t squared"
    assert _inline("∂𝑦/∂𝑡") == "partial y over partial t"


def test_non_derivative_stacked_fraction_keeps_the_wrapper_math_3() -> None:
    said = _stacked([_run("𝑎+𝑏", 225.9, 303.3)], [_run("𝑐", 228.0, 316.9)])
    assert said.startswith("the fraction a plus b over c, end fraction")
    said = _stacked([_run("𝑑𝑡", 225.9, 303.3)], [_run("𝑛", 228.0, 316.9)])
    assert said.startswith("the fraction d t over n, end fraction")


def test_text_font_sign_with_number_is_a_maths_gap_math_2() -> None:
    assert ms._maths_gap("+2")
    assert ms._maths_gap(" −1.5 ")
    assert not ms._maths_gap(" 2 ")
    assert not ms._maths_gap(" and ")
