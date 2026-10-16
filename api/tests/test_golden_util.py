from tests.golden_util import norm, seq_levenshtein


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
