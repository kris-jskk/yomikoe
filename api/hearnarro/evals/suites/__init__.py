"""Suite registry (D32): each suite module exposes ID, TITLE, TIER, dataset(), score(example)
and aggregate(scores). Tier 0 needs no model; tier 1 needs Kokoro; tier 2 is a human session.

A module may set ``DIRECTION`` to ``"lower"`` when a smaller score is better (EVAL-3 counts
junk); the default is ``"higher"``. The runner writes it into the record and ``store.compare``
honours it (D33). A module may also set ``METRIC_RULES``: ``{metric: (direction, tolerance,
relative)}`` for example metrics that differ from the suite default (EVAL-6's share improves
upwards; timings use a 10 % relative tolerance; direction ``"none"`` is not compared).
"""

from __future__ import annotations

from types import ModuleType

from hearnarro.evals.suites import (
    eval1_order,
    eval2_boundaries,
    eval3_clean,
    eval4_speech_form,
    eval5_intelligibility,
    eval6_sync,
    eval7_speed,
    eval8_ocr,
    eval9_listening,
)

SUITES: dict[str, ModuleType] = {
    m.ID: m
    for m in (
        eval1_order,
        eval2_boundaries,
        eval3_clean,
        eval4_speech_form,
        eval5_intelligibility,
        eval6_sync,
        eval7_speed,
        eval8_ocr,
        eval9_listening,
    )
}


def direction(suite_id: str) -> str:
    """``"higher"`` or ``"lower"``: which way a suite's scores improve (default higher)."""
    module = SUITES.get(suite_id)
    return getattr(module, "DIRECTION", "higher") if module else "higher"


def select(ids: list[str], tier: int) -> list[ModuleType]:
    """Resolve suite ids (or ``all``: every suite with TIER <= tier) to modules, in id order."""
    if "all" in ids:
        return [m for _, m in sorted(SUITES.items()) if m.TIER <= tier]
    unknown = [i for i in ids if i not in SUITES]
    if unknown:
        raise KeyError(f"unknown suite(s): {', '.join(unknown)}; known: {', '.join(SUITES)}")
    return [SUITES[i] for i in dict.fromkeys(ids)]
