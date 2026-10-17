"""Pure scoring functions shared by the gate tests and the eval suites (D31, D32).

Moved from ``tests/golden_util.py`` (reading order, D11/D12/D14, ING-4) and
``tests/boundary_util.py`` (sentence boundaries, ING-5, SYN-1); both helpers re-export these
names so the gate tests and the evals score with one definition.

Boundary metric: a boundary is the index of the word after which a sentence ends, counted over
the D14 word stream (``words``). The parser's word stream is aligned to the truth's with the
word-level edit script; a parser boundary matches when the word it follows aligns to an
expected word that ends a truth sentence. Words the parser inserts align to the expected word
before them, so an inserted word never shifts later boundaries.
"""

from __future__ import annotations

import re
import string
from collections.abc import Iterable
from typing import Any

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


def excluded_actual_texts(blocks: Iterable[Any], segments: Iterable[Any]) -> list[str]:
    """D14 guard, actual side, after ING-7: table and equation blocks speak cues, so their
    character mass is taken from the block's raw merged text (``LogicalBlock.raw_text``, once
    per block) rather than from the cue segments; other excluded blocks keep their segment text.
    """
    by_id = {b.id: b for b in blocks}
    out: list[str] = []
    for b in by_id.values():
        if b.type not in PROSE_TYPES and b.raw_text is not None:
            out.append(norm(b.raw_text))
    for s in segments:
        b = by_id[s.block_id]
        if b.type not in PROSE_TYPES and b.raw_text is None:
            out.append(norm(s.text))
    return out


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


def sentence_words(sentences: list[str]) -> list[str]:
    """The D14 word stream of a list of sentences."""
    return words(sentences)


def boundaries(sentences: list[str]) -> set[int]:
    """Word index after which each sentence ends; sentences with no words add none."""
    out: set[int] = set()
    count = 0
    for sentence in sentences:
        count += len(words([sentence]))
        if count:
            out.add(count - 1)
    return out


def _alignment(actual: list[str], expected: list[str]) -> list[int]:
    """For each actual word, the expected index it aligns to (-1 before the first expected word).

    Levenshtein edit script (insert/delete/substitute = 1); substituted and matched words align
    to their partner, inserted words to the expected word before them. A common prefix and
    suffix are aligned directly so the quadratic table covers only the differing middle.
    """
    n, m = len(actual), len(expected)
    pre = 0
    while pre < n and pre < m and actual[pre] == expected[pre]:
        pre += 1
    suf = 0
    while suf < n - pre and suf < m - pre and actual[n - 1 - suf] == expected[m - 1 - suf]:
        suf += 1
    a, b = actual[pre : n - suf], expected[pre : m - suf]
    la, lb = len(a), len(b)
    # back[i][j]: 0 diagonal, 1 delete (expected word skipped), 2 insert (actual word extra)
    back = [bytearray(lb + 1) for _ in range(la + 1)]
    for j in range(1, lb + 1):
        back[0][j] = 1
    prev = list(range(lb + 1))
    for i in range(1, la + 1):
        cur = [i] + [0] * lb
        row = back[i]
        row[0] = 2
        x = a[i - 1]
        for j in range(1, lb + 1):
            diag = prev[j - 1] + (x != b[j - 1])
            dele = cur[j - 1] + 1
            ins = prev[j] + 1
            best = diag
            step = 0
            if dele < best:
                best, step = dele, 1
            if ins < best:
                best, step = ins, 2
            cur[j] = best
            row[j] = step
        prev = cur
    mid = [0] * la
    i, j = la, lb
    while i > 0:
        step = back[i][j] if j > 0 else 2
        if step == 0:
            mid[i - 1] = j - 1
            i, j = i - 1, j - 1
        elif step == 1:
            j -= 1
        else:
            mid[i - 1] = j - 1
            i -= 1
    out = list(range(pre))
    out += [pre + k for k in mid]
    out += [m - suf + k for k in range(suf)]
    return out


def align_boundaries(
    actual_words: list[str],
    expected_words: list[str],
    actual_bounds: set[int],
    expected_bounds: set[int],
) -> tuple[int, int, int]:
    """(true positives, false positives, false negatives) of actual vs expected boundaries."""
    mapping = _alignment(actual_words, expected_words)
    matched: set[int] = set()
    for index in sorted(actual_bounds):
        target = mapping[index]
        if target in expected_bounds and target not in matched:
            matched.add(target)
    tp = len(matched)
    return tp, len(actual_bounds) - tp, len(expected_bounds) - tp


def prf(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    """Precision, recall and F1; 0.0 where a denominator is zero."""
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return precision, recall, f1


def matched_pairs(actual: list[str], expected: list[str]) -> list[tuple[int, int]]:
    """(actual index, expected index) of words the edit script aligns and that are equal;
    each expected word is used once (EVAL-6 sync)."""
    pairs: list[tuple[int, int]] = []
    used: set[int] = set()
    for i, j in enumerate(_alignment(actual, expected)):
        if 0 <= j < len(expected) and j not in used and actual[i] == expected[j]:
            used.add(j)
            pairs.append((i, j))
    return pairs


def percentile(values: list[float], q: float) -> float:
    """Nearest-rank percentile (q in 0..100) of a non-empty list."""
    ordered = sorted(values)
    rank = max(1, -(-len(ordered) * q // 100))
    return ordered[int(rank) - 1]
