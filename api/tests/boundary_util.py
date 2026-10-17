"""Sentence-boundary metric over the word stream (ING-5, SYN-1; M2 boundary truth).

A boundary is the index of the word after which a sentence ends, counted over the D14 word
stream (`golden_util.words`). The parser's word stream is aligned to the truth's with the
word-level edit script; a parser boundary matches when the word it follows aligns to an
expected word that ends a truth sentence. Words the parser inserts align to the expected word
before them, so an inserted word never shifts later boundaries.
"""

from __future__ import annotations

from tests.golden_util import words


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
