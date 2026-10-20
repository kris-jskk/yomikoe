"""MATH-2 (m5 p3i, gate b): a lone italic letter in upright prose is an inline variable."""

from __future__ import annotations

from hearnarro.ingestion.merge import _inline_spans, _italic_variables, _math_runs
from hearnarro.ingestion.models import BBox, Line, Span

_BOX = BBox(0.0, 0.0, 10.0, 10.0)


def _line(*parts: tuple[str, str]) -> Line:
    spans = [Span(t, _BOX, f, 10.0, italic="Italic" in f) for t, f in parts]
    return Line(spans, _BOX)


ROMAN, ITALIC = "LiberationSerif", "LiberationSerif-Italic"


def test_math2_italic_letter_in_prose_is_a_variable() -> None:
    line = _line(("the denominator is ", ROMAN), ("N", ITALIC), (", the number", ROMAN))
    assert _italic_variables(line) == {1}
    assert _math_runs(line) == [[1]]


def test_math2_italic_phrase_is_emphasis_not_a_variable() -> None:
    line = _line(("this is ", ROMAN), ("a", ITALIC), (" priori", ITALIC), (" known", ROMAN))
    assert _italic_variables(line) == set()


def test_math2_italic_word_is_not_a_variable() -> None:
    line = _line(("we call it ", ROMAN), ("deviation", ITALIC), (" here", ROMAN))
    assert _math_runs(line) == []


def test_math2_all_italic_line_has_no_variables() -> None:
    assert _italic_variables(_line(("x", ITALIC), (" is", ITALIC))) == set()


def test_math2_calligraphic_slant_letter_is_a_variable() -> None:
    line = _line(("Let ", ROMAN), ("F", "BoondoxCalligraphic-Regular-Slant_-300"), (" be", ROMAN))
    assert _italic_variables(line) == {1}


def test_math2_variable_span_ends_at_its_letter_and_accent_drops_runs() -> None:
    line = _line(("The symbol ", ROMAN), ("x ", ITALIC), ("is the mean", ROMAN))
    (sp,) = _inline_spans([line], [line.text], False)
    assert line.text[sp.start : sp.end] == "x" and sp.runs
    acc = _line(("The symbol ", ROMAN), ("x", ITALIC), ("¯", "STIXGeneral-Regular"), ("is", ROMAN))
    (sp,) = _inline_spans([acc], [acc.text], False)
    assert acc.text[sp.start : sp.end] == "x¯" and sp.runs == []


def test_math2_variable_span_is_one_slanted_letter() -> None:
    from hearnarro.ingestion.merge import _variable_span
    from hearnarro.ingestion.models import MathSpan

    x = Span("x", _BOX, ITALIC, 10.0, italic=True)
    sq = Span("2", _BOX, ROMAN, 7.0, superscript=True)
    frag = Span("q)] = O(1)", _BOX, ITALIC, 10.0, italic=True)
    assert _variable_span(MathSpan(0, 2, False, [x, sq]))
    assert not _variable_span(MathSpan(0, 10, False, [frag]))  # a joined fragment keeps its span
