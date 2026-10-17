"""EVAL-2 Boundaries: are sentences split where a reader would pause? (ING-5, SYN-1; D18)

Dataset: the 15 non-scanned fixtures and their reviewed ``*.sentences.txt``. Score: boundary
precision, recall and F1 over the aligned word stream (``align_boundaries``, ``prf``); the
example's ``score`` is its F1.
"""

from __future__ import annotations

from typing import Any

from hearnarro.evals.scorers import align_boundaries, boundaries, prf, sentence_words
from hearnarro.evals.suites import _fixtures

ID = "EVAL-2"
TITLE = "Boundaries"
TIER = 0


def dataset() -> list[dict[str, Any]]:
    """One example per non-scanned manifest entry."""
    return [
        {"id": e["name"], "class": e["class"], "skip": None}
        for e in _fixtures.entries(_fixtures.M1_CLASSES, skip_scanned=True)
    ]


def score(example: dict[str, Any]) -> dict[str, Any]:
    """Score one fixture: id, class, score (= f1), precision, recall, f1."""
    name = example["id"]
    truth = _fixtures.truth_sentences(name)
    actual = list(_fixtures.ingested(name)[0])
    tp, fp, fn = align_boundaries(
        sentence_words(actual), sentence_words(truth), boundaries(actual), boundaries(truth)
    )
    precision, recall, f1 = prf(tp, fp, fn)
    return {
        "id": name,
        "class": example["class"],
        "score": f1,
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }


def aggregate(scores: list[dict[str, Any]]) -> dict[str, Any]:
    """mean F1 and min recall."""
    if not scores:
        return {"mean_f1": 0.0, "min_recall": 0.0}
    return {
        "mean_f1": sum(s["f1"] for s in scores) / len(scores),
        "min_recall": min(s["recall"] for s in scores),
    }
