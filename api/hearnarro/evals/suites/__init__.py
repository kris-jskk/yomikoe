"""Suite registry (D32): each suite module exposes ID, TITLE, TIER, dataset(), score(example)
and aggregate(scores). Tier 0 needs no model; tier 1 needs Kokoro; tier 2 is a human session.
"""

from __future__ import annotations

from types import ModuleType

from hearnarro.evals.suites import eval1_order, eval2_boundaries

SUITES: dict[str, ModuleType] = {m.ID: m for m in (eval1_order, eval2_boundaries)}


def select(ids: list[str], tier: int) -> list[ModuleType]:
    """Resolve suite ids (or ``all``: every suite with TIER <= tier) to modules, in id order."""
    if "all" in ids:
        return [m for _, m in sorted(SUITES.items()) if m.TIER <= tier]
    unknown = [i for i in ids if i not in SUITES]
    if unknown:
        raise KeyError(f"unknown suite(s): {', '.join(unknown)}; known: {', '.join(SUITES)}")
    return [SUITES[i] for i in dict.fromkeys(ids)]
