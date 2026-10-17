"""EVAL-3 Clean text: how much junk reaches the voice? (ING-1 to ING-6; D31)

Dataset: the 15 non-scanned fixtures. Score: every check of the M1 quality checklist
(``hearnarro.quality.check_pdf`` -> ``run_checks``), its count and its rate per 1 000 words of
the document's segments (``words`` = whitespace words of every segment text, all block types,
from the cached ingest in ``_fixtures``). ``total_rate`` is the sum of the check rates and is
the example's ``score``. Lower is better (``DIRECTION``), so ``store.compare`` reports a rise
of more than 1 per 1 000 words as a regression.
"""

from __future__ import annotations

from typing import Any

from hearnarro.evals.suites import _fixtures

ID = "EVAL-3"
TITLE = "Clean text"
TIER = 0
DIRECTION = "lower"


def dataset() -> list[dict[str, Any]]:
    """One example per non-scanned manifest entry."""
    return [
        {"id": e["name"], "class": e["class"], "skip": None}
        for e in _fixtures.manifest()
        if e["class"] != "scanned"
    ]


def score(example: dict[str, Any]) -> dict[str, Any]:
    """id, class, words, checks {name: {count, rate}}, total_count, total_rate, score."""
    from hearnarro.quality import check_pdf

    name = example["id"]
    report = check_pdf(_fixtures.FIXTURES / f"{name}.pdf", ocr=False)
    words = sum(len(s.text.split()) for s in _fixtures.ingest_result(name).segments)
    per = 1000 / words if words else 0.0
    checks = {c.name: {"count": c.count, "rate": c.count * per} for c in report.checks}
    total_rate = sum(c["rate"] for c in checks.values())
    return {
        "id": name,
        "class": example["class"],
        "words": words,
        "checks": checks,
        "total_count": sum(c["count"] for c in checks.values()),
        "total_rate": total_rate,
        "score": total_rate,
    }


def aggregate(scores: list[dict[str, Any]]) -> dict[str, Any]:
    """Per-check mean rate and the mean total rate (per 1 000 words; lower is better)."""
    if not scores:
        return {"mean_rate": {}, "total_mean_rate": 0.0}
    names = list(scores[0]["checks"])
    return {
        "mean_rate": {n: sum(s["checks"][n]["rate"] for s in scores) / len(scores) for n in names},
        "total_mean_rate": sum(s["total_rate"] for s in scores) / len(scores),
    }
