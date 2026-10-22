"""Unit tests for ``yomikoe.evals.scorers.mathspeak_score`` (EVAL-10, MATH-1..4, M5 gate b)."""

from __future__ import annotations

import pytest

from yomikoe.evals.scorers import mathspeak_score


def test_eval10_mathspeak_score_identical_is_one() -> None:
    text = ["The sum from i equals 1 to n of x sub i."]
    assert mathspeak_score(text, text) == 1.0


def test_eval10_mathspeak_score_ignores_case_and_punctuation() -> None:
    assert mathspeak_score(["X squared, plus Y."], ["x squared plus y"]) == 1.0


def test_eval10_mathspeak_score_empty_expected() -> None:
    assert mathspeak_score([], []) == 1.0
    assert mathspeak_score(["equation"], []) == 0.0


def test_eval10_mathspeak_score_partial_match() -> None:
    # one substitution in four expected words
    assert mathspeak_score(["x squared plus z"], ["x squared plus y"]) == pytest.approx(0.75)
    # the ING-7 cue against a spoken expression: clamped, never negative
    assert mathspeak_score(["Equation one two three four five six."], ["x squared"]) == 0.0


def test_eval10_mathspeak_score_accepts_texts_or_words() -> None:
    words = ["a", "over", "b"]
    assert mathspeak_score(words, ["a over b"]) == mathspeak_score(["a over b"], words) == 1.0
