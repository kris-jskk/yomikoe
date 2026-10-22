"""ING-6 / MATH-1 (M5 listening sheet 2026-10-22, formula_10): in a segment that carries maths
(an equation block, or a body segment with a maths range) a dash glued to the front of a number
and preceded by "(", "[" or a space reads "minus"; a dash between two digits keeps the range
rule; prose without maths is unchanged."""

from __future__ import annotations

import pytest

from yomikoe.ingestion.mathspeak import speak_segment
from yomikoe.ingestion.normalize import normalize


def _round_trip(text: str, norm: str, cmap: list[int]) -> None:
    assert len(cmap) == len(norm)
    assert cmap == sorted(cmap) and all(0 <= c < len(text) for c in cmap)


@pytest.mark.parametrize("dash", ["—", "–", "−", "-"])
def test_ing6_dash_before_number_in_maths_reads_minus(dash: str) -> None:
    text = f"deviations ({dash}0.670) below"
    norm, cmap = normalize(text, maths=True)
    assert norm == "deviations (minus 0.670) below"
    _round_trip(text, norm, cmap)
    i = norm.index("minus")
    assert {cmap[k] for k in range(i, i + 6)} == {text.index(dash)}


def test_ing6_dash_after_space_or_bracket_reads_minus() -> None:
    assert normalize("x = —5", maths=True)[0] == "x equals minus 5"
    assert normalize("t in [–2, 3]", maths=True)[0] == "t in [minus 2, 3]"


@pytest.mark.parametrize("text", ["the years 2010—2015", "rows 3-5", "x2 –3 apart", "COVID-19"])
def test_ing6_dash_between_digits_or_glued_stays(text: str) -> None:
    assert "minus" not in normalize(text, maths=True)[0]
    assert normalize(text, maths=True) == normalize(text)


def test_ing6_dash_minus_prose_unchanged() -> None:
    assert normalize("deviations (—0.670) below")[0] == "deviations (—0.670) below"


def test_ing6_dash_minus_through_mathspeak_segment() -> None:
    text = "Then x = 1 is 0.67 deviations (—0.670) below the mean."
    s = text.index("x = 1")
    norm, cmap = speak_segment(text, [{"start": s, "end": s + 5, "display": False}])
    assert "(minus 0.670)" in norm
    _round_trip(text, norm, cmap)
    assert "minus" not in speak_segment("Deviations (—0.670) below the mean.", [])[0]
