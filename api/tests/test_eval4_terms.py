"""EVAL-4 term_* scoring (spec m5-academic-reading §8 Q8; TERM-1, TERM-2): for every ``term_*``
category ``score`` is the joined phoneme similarity, ``partial`` and ``exact`` are kept; other
categories keep ``score`` = ``partial``."""

from __future__ import annotations

import pytest

from hearnarro.evals.suites import eval4_speech_form as e4


def test_eval4_joined_similarity_ignores_spaces_and_stress() -> None:
    assert e4.joined_similarity(["kˈOʃi"], ["kˈO", "ʃˈi"]) == 1.0
    assert e4.joined_similarity(["ab"], ["ac"]) == 0.5
    assert e4.joined_similarity([], ["ab"]) == 0.0
    assert e4.joined_similarity(["abcdef"], ["a"]) == 0.0  # floored at 0


needs_g2p = pytest.mark.skipif(e4.unavailable() is not None, reason="misaki unavailable")


@needs_g2p
def test_eval4_term_row_scores_joined_one_word_against_hyphenated() -> None:
    ex = {
        "id": "t",
        "class": "term_math",
        "text": "The Cauchy sequence is bounded.",
        "expected": "The Koh-shee sequence is bounded.",
    }
    s = e4.score(ex)
    assert s["score"] == 1.0
    assert s["joined"] == 1.0
    assert s["partial"] < 1.0
    assert s["exact"] is False


@needs_g2p
def test_eval4_non_term_row_score_equals_partial() -> None:
    ex = {
        "id": "n",
        "class": "abbreviation",
        "text": "The Cauchy sequence is bounded.",
        "expected": "The Koh-shee sequence is bounded.",
    }
    s = e4.score(ex)
    assert s["score"] == s["partial"] < 1.0
