"""Scoring helpers for the reading-order golden test (D11, ING-4)."""

from __future__ import annotations

import re
import string
from collections.abc import Iterable

# D12: the golden comparison keeps only these types; table and equation internals wait for
# ING-7 (M4), and figure/noise/header/footer text is never read.
PROSE_TYPES = frozenset({"heading", "body", "list", "caption", "footnote"})
# D14: excluded character mass must agree within this absolute difference on both sides.
CHAR_MASS_TOLERANCE = 0.05
# D14: stripped from each end of every token: ASCII punctuation plus curly quotes, en/em dash
# and ellipsis.
PUNCTUATION = string.punctuation + "\u2018\u2019\u201c\u201d\u2013\u2014\u2026"


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


def prose_only(items: Iterable[tuple[str, str]]) -> tuple[list[str], list[str]]:
    """Split (type, text) pairs into normalized prose texts and normalized excluded texts (D12)."""
    kept: list[str] = []
    excluded: list[str] = []
    for type_, text in items:
        (kept if type_ in PROSE_TYPES else excluded).append(norm(text))
    return kept, excluded


def words(texts: list[str]) -> list[str]:
    """D14 tokenization: join with spaces, lowercase, split, strip punctuation, drop empties."""
    out: list[str] = []
    for token in " ".join(texts).lower().split():
        token = token.strip(PUNCTUATION)
        if token:
            out.append(token)
    return out


def word_score(actual_texts: list[str], expected_texts: list[str]) -> float:
    """D14 score: 1 - word-sequence edit distance / number of expected words."""
    actual, expected = words(actual_texts), words(expected_texts)
    if not expected:
        raise ValueError("expected side has no words")
    return 1 - seq_levenshtein(actual, expected) / len(expected)


def char_mass_ratio(prose_texts: list[str], excluded_texts: list[str]) -> float:
    """D14 guard input: chars in excluded (table/equation) segments / chars in all segments."""
    excluded = sum(len(t) for t in excluded_texts)
    total = sum(len(t) for t in prose_texts) + excluded
    return excluded / total if total else 0.0


def char_mass_balanced(ratio_actual: float, ratio_expected: float) -> bool:
    """D14 guard: misclassifying prose as table/equation cannot hide an error."""
    return abs(ratio_actual - ratio_expected) <= CHAR_MASS_TOLERANCE
