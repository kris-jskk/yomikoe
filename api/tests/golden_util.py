"""Scoring helpers for the reading-order golden test (D11, ING-4)."""

from __future__ import annotations

import re


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
