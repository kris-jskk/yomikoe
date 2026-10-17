"""EVAL-1 Order: is the prose in the right order? (ING-3, ING-4, ING-5; D11, D12, D14)

Dataset: the 20 fixture PDFs and their ``*.expected.jsonl``; scanned fixtures are skipped when
tesseract is absent, as in the golden test. Score: ``word_score`` (1 - word edit distance /
expected words); the D14 char-mass guard is kept per example as ``char_mass_ok``.
"""

from __future__ import annotations

from typing import Any

from hearnarro.evals.scorers import char_mass_balanced, char_mass_ratio, prose_only, word_score
from hearnarro.evals.suites import _fixtures

ID = "EVAL-1"
TITLE = "Order"
TIER = 0


def dataset() -> list[dict[str, Any]]:
    """One example per manifest entry: id, class, and a skip reason or None."""
    from hearnarro.ingestion.extract import ocr_available

    ocr = ocr_available()
    out = []
    for e in _fixtures.manifest():
        skip = None
        if e["class"] == "scanned" and not ocr:
            skip = "OCR unavailable (tesseract)"
        out.append({"id": e["name"], "class": e["class"], "skip": skip})
    return out


def score(example: dict[str, Any]) -> dict[str, Any]:
    """Score one fixture: id, class, score, and the D14 char-mass guard."""
    name = example["id"]
    expected, excluded_expected = prose_only(_fixtures.expected_rows(name))
    actual, excluded_actual = _fixtures.ingested(name)
    ratio_actual = char_mass_ratio(list(actual), list(excluded_actual))
    ratio_expected = char_mass_ratio(expected, excluded_expected)
    return {
        "id": name,
        "class": example["class"],
        "score": word_score(list(actual), expected),
        "char_mass_ok": char_mass_balanced(ratio_actual, ratio_expected),
    }


def aggregate(scores: list[dict[str, Any]]) -> dict[str, Any]:
    """mean, min and mean per class of ``score``."""
    values = [s["score"] for s in scores]
    by_class: dict[str, list[float]] = {}
    for s in scores:
        by_class.setdefault(s["class"], []).append(s["score"])
    return {
        "mean": sum(values) / len(values) if values else 0.0,
        "min": min(values) if values else 0.0,
        "by_class": {c: sum(v) / len(v) for c, v in sorted(by_class.items())},
    }
