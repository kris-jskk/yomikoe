from tests.golden_util import exclusion_balanced, norm, prose_only, seq_levenshtein


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
    assert (exp_excluded, act_excluded) == (1, 1)
    assert seq_levenshtein(act_texts, exp_texts) == 0
    assert exclusion_balanced(act_excluded, exp_excluded)


def test_ing4_d12_exclusion_balance_guard() -> None:
    assert exclusion_balanced(0, 0)
    assert not exclusion_balanced(1, 0)  # tolerance 0.15 * max(1, 0)
    assert exclusion_balanced(115, 100) and exclusion_balanced(85, 100)
    assert not exclusion_balanced(116, 100) and not exclusion_balanced(84, 100)
    # prose misread as table: the prose sequence would shrink, the guard catches it
    assert not exclusion_balanced(40, 20)
