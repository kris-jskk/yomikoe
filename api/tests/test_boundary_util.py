"""Unit tests for the sentence-boundary metric (ING-5, SYN-1; M2 boundary truth)."""

import pytest

from tests.boundary_util import align_boundaries, boundaries, prf, sentence_words


def _score(actual: list[str], expected: list[str]) -> tuple[int, int, int]:
    return align_boundaries(
        sentence_words(actual), sentence_words(expected), boundaries(actual), boundaries(expected)
    )


def test_ing5_boundaries_word_index_after_each_sentence() -> None:
    assert boundaries(["One two three.", "Four five.", "Six."]) == {2, 4, 5}


def test_ing5_boundaries_skip_sentences_without_words() -> None:
    assert boundaries(["One two.", "—", "Three."]) == {1, 2}


def test_ing5_identical_sentences_score_perfect() -> None:
    sents = ["A cat sat.", "It purred loudly.", "Then it slept."]
    tp, fp, fn = _score(sents, sents)
    assert (tp, fp, fn) == (3, 0, 0)
    assert prf(tp, fp, fn) == (1.0, 1.0, 1.0)


def test_ing5_extra_split_is_one_false_positive() -> None:
    expected = ["See Fig. 2 for details.", "It held."]
    actual = ["See Fig.", "2 for details.", "It held."]
    assert _score(actual, expected) == (2, 1, 0)


def test_ing5_missed_split_is_one_false_negative() -> None:
    expected = ["It rained.", "We stayed in.", "The end."]
    actual = ["It rained. We stayed in.", "The end."]
    assert _score(actual, expected) == (2, 0, 1)


def test_ing5_inserted_word_does_not_shift_later_boundaries() -> None:
    expected = ["Alpha beta gamma.", "Delta epsilon."]
    actual = ["Alpha beta EXTRA gamma.", "Delta epsilon."]
    assert _score(actual, expected) == (2, 0, 0)


def test_ing5_boundary_after_inserted_word_maps_to_preceding_expected_word() -> None:
    expected = ["Alpha beta.", "Gamma delta."]
    actual = ["Alpha beta junk.", "Gamma delta."]
    # "junk" aligns after "beta", so the boundary after it is the boundary after "beta".
    assert _score(actual, expected) == (2, 0, 0)


def test_ing5_deleted_word_with_split_elsewhere() -> None:
    expected = ["Alpha beta gamma.", "Delta epsilon."]
    actual = ["Alpha gamma.", "Delta.", "Epsilon."]
    assert _score(actual, expected) == (2, 1, 0)


def test_ing5_prf_values_and_zero_division() -> None:
    p, r, f = prf(3, 1, 2)
    assert p == pytest.approx(0.75)
    assert r == pytest.approx(0.6)
    assert f == pytest.approx(2 * 0.75 * 0.6 / 1.35)
    assert prf(0, 0, 0) == (0.0, 0.0, 0.0)
