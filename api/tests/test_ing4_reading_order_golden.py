"""M1 gate: reading-order golden test over the 20 fixture PDFs (D11, ING-4, ING-5).

score = 1 - levenshtein(actual_seq, expected_seq) / len(expected_seq), sequences of
whitespace-collapsed segment texts. Gate: >= 0.95 per PDF and >= 0.97 mean.
"""

import json
from collections import Counter
from functools import cache
from pathlib import Path

import pytest

from hearnarro.ingestion.extract import ocr_available
from hearnarro.ingestion.pipeline import ingest
from tests.golden_util import norm, seq_levenshtein

FIXTURES = Path(__file__).parent / "fixtures" / "pdfs"
MANIFEST = FIXTURES / "manifest.json"
CLASSES = ("academic", "report", "scanned", "tables")
PER_PDF_MIN = 0.95
MEAN_MIN = 0.97

if not MANIFEST.exists():
    pytest.skip(f"{MANIFEST} missing: fixture PDFs not added yet", allow_module_level=True)

ENTRIES: list[dict] = json.loads(MANIFEST.read_text())
BY_NAME = {e["name"]: e for e in ENTRIES}


def _expected_path(name: str) -> Path:
    return FIXTURES / f"{name}.expected.jsonl"


def _skip_reason(entry: dict) -> str | None:
    if not _expected_path(entry["name"]).exists():
        return f"{entry['name']}.expected.jsonl missing"
    if entry["class"] == "scanned" and not ocr_available():
        return "OCR unavailable (tesseract); scanned fixtures need OCR fallback (M4)"
    return None


@cache
def _score(name: str) -> float:
    expected = [
        norm(json.loads(line)["text"])
        for line in _expected_path(name).read_text().splitlines()
        if line.strip()
    ]
    result = ingest(FIXTURES / f"{name}.pdf", document_id=0, ocr=True)
    actual = [norm(s.text) for s in result.segments]
    assert expected, f"{name}.expected.jsonl is empty"
    return 1 - seq_levenshtein(actual, expected) / len(expected)


def test_fixture_set_complete() -> None:
    assert len(ENTRIES) == 20
    assert Counter(e["class"] for e in ENTRIES) == {c: 5 for c in CLASSES}
    for e in ENTRIES:
        assert (FIXTURES / f"{e['name']}.pdf").exists(), e["name"]
        assert _expected_path(e["name"]).exists(), e["name"]


@pytest.mark.parametrize("name", sorted(BY_NAME))
def test_reading_order_golden(name: str) -> None:
    entry = BY_NAME[name]
    reason = _skip_reason(entry)
    if reason:
        pytest.skip(reason)
    score = _score(name)
    print(f"{name}\t{entry['class']}\t{score:.4f}")
    assert score >= PER_PDF_MIN, f"{name} ({entry['class']}): {score:.4f} < {PER_PDF_MIN}"


def test_reading_order_mean() -> None:
    scored = [e["name"] for e in ENTRIES if _skip_reason(e) is None]
    if not scored:
        pytest.skip("no scoreable fixtures")
    scores = [_score(n) for n in scored]
    mean = sum(scores) / len(scores)
    print(f"mean over {len(scores)} fixtures: {mean:.4f}")
    assert mean >= MEAN_MIN, f"mean {mean:.4f} < {MEAN_MIN}"
