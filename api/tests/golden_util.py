"""Scoring helpers for the reading-order golden test (D11, ING-4)."""

from __future__ import annotations

import re
from collections.abc import Iterable

# D12: the golden comparison keeps only these types; table and equation internals wait for
# ING-7 (M4), and figure/noise/header/footer text is never read.
PROSE_TYPES = frozenset({"heading", "body", "list", "caption", "footnote"})
EXCLUSION_TOLERANCE = 0.15


def norm(text: str) -> str:
    """Collapse runs of whitespace to one space and strip the ends."""
    return re.sub(r"\s+", " ", text).strip()


def seq_levenshtein(a: list[str], b: list[str]) -> int:
    """Edit distance between two sequences, elements compared whole (insert/delete/substitute = 1)."""
    prev = list(range(len(b) + 1))
    for i, x in enumerate(a, start=1):
        cur = [i] + [0] * len(b)
        for j, y in enumerate(b, start=1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (x != y))
        prev = cur
    return prev[len(b)]


def prose_only(items: Iterable[tuple[str, str]]) -> tuple[list[str], int]:
    """Split (type, text) pairs into the normalized prose texts and the count excluded (D12)."""
    kept: list[str] = []
    excluded = 0
    for type_, text in items:
        if type_ in PROSE_TYPES:
            kept.append(norm(text))
        else:
            excluded += 1
    return kept, excluded


def exclusion_balanced(excluded_actual: int, excluded_expected: int) -> bool:
    """D12 guard: misclassifying prose as table/equation cannot hide an error.

    |excluded_actual - excluded_expected| <= EXCLUSION_TOLERANCE * max(1, excluded_expected).
    """
    tolerance = EXCLUSION_TOLERANCE * max(1, excluded_expected)
    return abs(excluded_actual - excluded_expected) <= tolerance
