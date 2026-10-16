import pytest

from tests.golden_util import (
    char_mass_balanced,
    char_mass_ratio,
    norm,
    prose_only,
    seq_levenshtein,
    word_score,
    words,
)


def test_seq_levenshtein_identical_is_zero() -> None:
    assert seq_levenshtein(["a", "b", "c"], ["a", "b", "c"]) == 0


def test_seq_levenshtein_swap_costs_two() -> None:
    assert seq_levenshtein(["a", "b", "c"], ["b", "a", "c"]) == 2


def test_seq_levenshtein_insert_delete_substitute() -> None:
    assert seq_levenshtein([], ["x", "y"]) == 2
    assert seq_levenshtein(["x", "y"], []) == 2
    assert seq_levenshtein(["a", "b", "c"], ["a", "z", "c", "d"]) == 2


def test_norm_collapses_whitespace() -> None:
    assert norm("  a \n b\t c  ") == "a b c"


def test_ing4_d12_prose_only_three_line_case() -> None:
    expected = [("heading", "1 Intro"), ("table", "a | b"), ("body", "Some  text.")]
    actual = [("heading", "1 Intro"), ("body", "Some text."), ("equation", "x = 1")]
    exp_texts, exp_excluded = prose_only(expected)
    act_texts, act_excluded = prose_only(actual)
    assert exp_texts == act_texts == ["1 Intro", "Some text."]
    assert (exp_excluded, act_excluded) == (["a | b"], ["x = 1"])
    assert seq_levenshtein(act_texts, exp_texts) == 0


def test_ing4_d14_words_strips_ascii_punctuation_and_lowercases() -> None:
    assert words(["Hello, World!", "(see Fig. 3)."]) == ["hello", "world", "see", "fig", "3"]


def test_ing4_d14_words_strips_typographic_punctuation() -> None:
    texts = ["“Quoted” ‘single’ a— –b wait…"]
    assert words(texts) == ["quoted", "single", "a", "b", "wait"]


def test_ing4_d14_words_drops_empty_tokens_and_keeps_inner_punctuation() -> None:
    assert words(["a - b — … ...", "", "  "]) == ["a", "b"]
    assert words(["don't e.g. x-ray"]) == ["don't", "e.g", "x-ray"]


def test_ing4_d14_segment_boundaries_do_not_matter() -> None:
    assert word_score(["One two.", "Three four."], ["One two. Three", "four."]) == 1.0


def test_ing4_d14_word_score_three_word_edit_case() -> None:
    # expected 3 words; actual substitutes one -> 1 - 1/3
    assert word_score(["The quick fox"], ["The slow fox."]) == pytest.approx(2 / 3)
    # dropping one word and adding one elsewhere costs two edits
    assert word_score(["quick fox jumps"], ["The quick fox"]) == pytest.approx(1 - 2 / 3)


def test_ing4_d14_char_mass_ratio() -> None:
    assert char_mass_ratio(["abcdef"], ["ab", "cd"]) == pytest.approx(4 / 10)
    assert char_mass_ratio(["abc"], []) == 0.0
    assert char_mass_ratio([], []) == 0.0


def test_ing4_d14_char_mass_guard() -> None:
    assert char_mass_balanced(0.10, 0.15)
    assert char_mass_balanced(0.0, 0.0)
    assert not char_mass_balanced(0.10, 0.16)
    # prose misread as table: the excluded share grows, the guard catches it
    assert not char_mass_balanced(char_mass_ratio(["a" * 50], ["b" * 50]), 0.0)
