"""EVAL-8 OCR: how accurate is the scanned path? (ING-2; D31, D34)

Dataset: the 5 ``scanned`` fixtures of ``tests/fixtures/pdfs/manifest.json``. Each runs the
existing extraction path with OCR (``_fixtures.ingested``, the same cached ``ingest(...,
ocr=True)`` EVAL-1 uses), keeps the prose segments (``scorers.prose_only``, as EVAL-1), joins
them with single spaces, and compares with the joined prose of ``<name>.expected.jsonl``.

Score: character error rate (``scorers.char_error_rate``: char edit distance / expected
characters), lower is better. When ``ocr_available()`` is false every example is skipped
with the reason and nothing is scored (tesseract is not installed by the suite).
"""

from __future__ import annotations

from typing import Any

from hearnarro.evals.scorers import char_error_rate, prose_only
from hearnarro.evals.suites import _fixtures

ID = "EVAL-8"
TITLE = "OCR"
TIER = 1
DIRECTION = "lower"
SKIP_REASON = "OCR unavailable (tesseract)"
# D33: the character counts are context, not compared.
METRIC_RULES: dict[str, tuple[str, float, bool]] = {
    "expected_chars": ("none", 0.0, False),
    "actual_chars": ("none", 0.0, False),
}


def _joined(texts: list[str] | tuple[str, ...]) -> str:
    return " ".join(" ".join(t.split()) for t in texts if t.strip())


def dataset() -> list[dict[str, Any]]:
    """One example per scanned fixture; all skipped with the reason when OCR is unavailable."""
    from hearnarro.ingestion import extract

    skip = None if extract.ocr_available() else SKIP_REASON
    return [
        {"id": e["name"], "class": e["class"], "skip": skip}
        for e in _fixtures.manifest()
        if e["class"] == "scanned"
    ]


def score(example: dict[str, Any]) -> dict[str, Any]:
    name = example["id"]
    expected, _ = prose_only(_fixtures.expected_rows(name))
    actual, _ = _fixtures.ingested(name)
    exp, act = _joined(expected), _joined(actual)
    value = char_error_rate(act, exp)
    return {
        "id": name,
        "class": example["class"],
        "cer": value,
        "score": value,
        "expected_chars": len(exp),
        "actual_chars": len(act),
    }


def aggregate(scores: list[dict[str, Any]]) -> dict[str, Any]:
    """Mean and max CER."""
    values = [s["cer"] for s in scores]
    return {
        "mean_cer": sum(values) / len(values) if values else 0.0,
        "max_cer": max(values) if values else 0.0,
    }
