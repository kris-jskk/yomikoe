"""M1 gate: reading-order golden test over the 20 fixture PDFs (D11, ING-4, ING-5).

D12 (prose-only): both sides keep only heading, body, list, caption and footnote segments.

D14 (word-level gate): score = 1 - levenshtein(actual_words, expected_words) / len(expected_words)
over the joined prose texts, lowercased, whitespace-split, punctuation stripped per token.
Gate: >= 0.95 per PDF (>= 0.85 for scanned_* fixtures, D35) and >= 0.97 mean. Guard: excluded (table/equation) character mass over
all characters agrees within 0.05 absolute on each side. The sentence-level score (segment
texts compared whole) is printed as a diagnostic and never asserted.
"""

import json
from collections import Counter
from dataclasses import dataclass
from functools import cache
from pathlib import Path

import pytest

from hearnarro.ingestion.extract import ocr_available
from hearnarro.ingestion.pipeline import ingest
from tests.golden_util import (
    CHAR_MASS_TOLERANCE,
    char_mass_balanced,
    char_mass_ratio,
    excluded_actual_texts,
    prose_only,
    seq_levenshtein,
    word_score,
)

FIXTURES = Path(__file__).parent / "fixtures" / "pdfs"
MANIFEST = FIXTURES / "manifest.json"
CLASSES = ("academic", "report", "scanned", "tables")
PER_PDF_MIN = 0.95
SCANNED_PER_PDF_MIN = 0.85  # D35: OCR misreads maths on scanned_04/05
MEAN_MIN = 0.97

if not MANIFEST.exists():
    pytest.skip(f"{MANIFEST} missing: fixture PDFs not added yet", allow_module_level=True)

ENTRIES: list[dict] = json.loads(MANIFEST.read_text())
BY_NAME = {e["name"]: e for e in ENTRIES}


def _expected_path(name: str) -> Path:
    return FIXTURES / f"{name}.expected.jsonl"


def _floor(name: str) -> float:
    return SCANNED_PER_PDF_MIN if name.startswith("scanned_") else PER_PDF_MIN


def _skip_reason(entry: dict) -> str | None:
    if not _expected_path(entry["name"]).exists():
        return f"{entry['name']}.expected.jsonl missing"
    if entry["class"] == "scanned" and not ocr_available():
        return "OCR unavailable (tesseract); scanned fixtures need OCR fallback (M4)"
    return None


@dataclass(frozen=True)
class Score:
    word: float  # D14 gate score
    sentence: float  # D12 sentence-level score, diagnostic only
    ratio_actual: float  # excluded character mass, actual side
    ratio_expected: float  # excluded character mass, expected side


@cache
def _score(name: str) -> Score:
    rows = [
        json.loads(line) for line in _expected_path(name).read_text().splitlines() if line.strip()
    ]
    expected, excluded_expected = prose_only((r["type"], r["text"]) for r in rows)
    result = ingest(FIXTURES / f"{name}.pdf", document_id=0, ocr=True)
    block_type = {b.id: b.type for b in result.blocks}
    actual, _ = prose_only((block_type[s.block_id], s.text) for s in result.segments)
    # ING-7: table/equation segments are cues; the guard weighs their blocks' raw text (D14).
    excluded_actual = excluded_actual_texts(result.blocks, result.segments)
    assert expected, f"{name}.expected.jsonl has no prose segments"
    return Score(
        word=word_score(actual, expected),
        sentence=1 - seq_levenshtein(actual, expected) / len(expected),
        ratio_actual=char_mass_ratio(actual, excluded_actual),
        ratio_expected=char_mass_ratio(expected, excluded_expected),
    )


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
    sc = _score(name)
    print(
        f"{name}\t{entry['class']}\tfloor={_floor(name):.2f} (text {PER_PDF_MIN}, scanned {SCANNED_PER_PDF_MIN})\tword={sc.word:.4f}\tsentence={sc.sentence:.4f}"
        f"\texcluded_chars actual={sc.ratio_actual:.4f} expected={sc.ratio_expected:.4f}"
    )
    assert sc.word >= _floor(name), f"{name} ({entry['class']}): {sc.word:.4f} < {_floor(name)}"
    assert char_mass_balanced(sc.ratio_actual, sc.ratio_expected), (
        f"{name}: excluded char mass actual={sc.ratio_actual:.4f} vs "
        f"expected={sc.ratio_expected:.4f} differs by more than {CHAR_MASS_TOLERANCE}"
    )


def test_reading_order_mean() -> None:
    scored = [e["name"] for e in ENTRIES if _skip_reason(e) is None]
    if not scored:
        pytest.skip("no scoreable fixtures")
    scores = [_score(n).word for n in scored]
    mean = sum(scores) / len(scores)
    sentence_mean = sum(_score(n).sentence for n in scored) / len(scored)
    print(
        f"word-level mean over {len(scores)} fixtures: {mean:.4f} (min {min(scores):.4f}); "
        f"sentence-level mean (diagnostic): {sentence_mean:.4f}"
    )
    assert mean >= MEAN_MIN, f"mean {mean:.4f} < {MEAN_MIN}"
