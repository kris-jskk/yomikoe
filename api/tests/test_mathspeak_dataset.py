"""EVAL-10 dataset through the mathspeak core (MATH-1..4, D36): char_map rule and scores."""

from __future__ import annotations

import pytest

from hearnarro.evals.scorers import mathspeak_score
from hearnarro.evals.suites.eval10_mathspeak import load_pairs
from hearnarro.ingestion.mathspeak import char_map_errors, speak_segment
from hearnarro.ingestion.mathspeak.markup import markup_segment

OVERALL_MIN = 0.85
CLASS_MIN = 0.80


def _run(pair: dict) -> tuple[str, str, list[int], list]:  # type: ignore[type-arg]
    text, spans = markup_segment(pair["raw"], pair["block"])
    out, cmap = speak_segment(text, spans)
    return text, out, cmap, spans


@pytest.mark.parametrize("pair", load_pairs(), ids=lambda p: p["id"])
def test_math2_char_map_rule_on_every_pair(pair: dict) -> None:  # type: ignore[type-arg]
    text, out, cmap, spans = _run(pair)
    assert char_map_errors(text, out, cmap, spans) == []


def test_eval10_dataset_scores_overall_and_per_class() -> None:
    by: dict[str, list[float]] = {}
    for pair in load_pairs():
        out = _run(pair)[1]
        by.setdefault(pair["class"], []).append(mathspeak_score([out], [pair["spoken"]]))
    values = [v for vs in by.values() for v in vs]
    assert len(values) == 158
    assert sum(values) / len(values) >= OVERALL_MIN
    for cls in ("display", "inline", "symbol", "reference"):
        assert sum(by[cls]) / len(by[cls]) >= CLASS_MIN, cls
