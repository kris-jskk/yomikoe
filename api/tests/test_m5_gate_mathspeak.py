"""M5 gate, clauses (a), (b), (e) (PRD "Milestones" item 5; spec
``_agent/specs/m5-academic-reading.md`` §0, §1a, §1d; MATH-1..4, ING-10, ING-11, EVAL-10).

(a) ten formula fixtures with pdf, expected.jsonl and a non-empty spoken.txt; (b) the spoken
mathematics score (``scorers.mathspeak_score``, D14-style) per fixture and its mean; (e) the
document profile class (``compute_profile``, ING-11) matches the manifest ``profile`` of the 30
fixtures for at least 28. Image-only documents need a real OCR engine and are ``@pytest.mark.ocr``,
skipped only on a machine without tesseract on PATH (spec §8, Q3).

Red until phase 2 (``compute_profile``, imported inside the test) and phase 3 (mathspeak) land; it
fails on assertions, never at collection.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from hearnarro.evals.suites import _fixtures
from hearnarro.evals.suites import eval10_mathspeak as eval10
from hearnarro.ingestion.extract import ocr_available

FORMULA_COUNT = 10
CUT_SOURCES = (
    "tables_01_pfn_bayes",
    "tables_03_copula_subspaces",
    "tables_04_markov_kernel",
    "tables_05_decomposing_learner",
    "academic_02_memduet",
)
MIN_TEXTBOOK = 2
CODE_PAGES = 2
SCORE_TEXT_LAYER = 0.90
SCORE_SCANNED = 0.75
SCORE_MEAN = 0.92
PROFILE_CLASSES = ("prose", "mixed", "math")
PROFILE_TOTAL = 30
PROFILE_MAX_MISMATCH = 2

FORMULA_STEMS = [e["name"] for e in eval10.formula_entries()]


def _exists(name: str, suffix: str) -> bool:
    return (_fixtures.FIXTURES / f"{name}{suffix}").exists()


def _code_blocks(name: str) -> int:
    path = _fixtures.FIXTURES / f"{name}.expected.jsonl"
    rows = [json.loads(ln) for ln in path.read_text().splitlines() if ln.strip()]
    return sum(r.get("type") == "code" for r in rows)


def _cut_from(entry: dict[str, Any]) -> str | None:
    """The existing fixture a formula page was cut from: named in its source, or its URL."""
    by_name = {e["name"]: e for e in _fixtures.manifest()}
    source = str(entry.get("source", ""))
    for stem in CUT_SOURCES:
        if stem in source or (stem in by_name and by_name[stem].get("source") == source):
            return stem
    return None


def test_m5_gate_a_formula_fixtures_present() -> None:
    entries = eval10.formula_entries()
    assert len(entries) == FORMULA_COUNT, f"{len(entries)} formula entries, need {FORMULA_COUNT}"
    missing = [
        f"{e['name']}{suffix}"
        for e in entries
        for suffix in (".pdf", ".expected.jsonl", ".spoken.txt")
        if not _exists(e["name"], suffix)
    ]
    assert not missing, f"missing fixtures: {missing}"
    empty = [e["name"] for e in entries if not eval10.spoken_lines(e["name"])]
    assert not empty, f"empty spoken.txt: {empty}"
    no_profile = [e["name"] for e in entries if e.get("profile") not in PROFILE_CLASSES]
    assert not no_profile, f"no manifest profile: {no_profile}"
    cut = {e["name"]: _cut_from(e) for e in entries}
    assert sorted(s for s in cut.values() if s) == sorted(CUT_SOURCES), cut
    new = [e["name"] for e in entries if not cut[e["name"]]]
    image_only = [n for n in new if not eval10.has_text_layer(n)]
    assert len(image_only) == 1, f"image-only new pages: {image_only}"
    assert all(eval10.has_text_layer(n) for n in cut if cut[n]), "a cut page lost its text layer"
    # 06..09 are textbook or technical-book pages (spec §1a): the new pages with a text layer.
    textbook = [n for n in new if n not in image_only]
    assert len(textbook) >= MIN_TEXTBOOK, textbook
    with_code = [n for n in new if _code_blocks(n) >= 1]
    assert len(with_code) >= CODE_PAGES, f"pages with a code block: {with_code}"


def _require_files(name: str) -> None:
    for suffix in (".pdf", ".spoken.txt"):
        if not _exists(name, suffix):
            pytest.fail(f"missing fixture {name}{suffix}")


def _ocr_case(name: str) -> bool:
    return _exists(name, ".pdf") and not eval10.has_text_layer(name)


@pytest.mark.parametrize(
    "stem",
    [pytest.param(n, marks=pytest.mark.ocr) if _ocr_case(n) else n for n in FORMULA_STEMS],
)
def test_m5_gate_b_spoken_maths_score(stem: str) -> None:
    _require_files(stem)
    scanned = not eval10.has_text_layer(stem)
    if scanned and not ocr_available():
        pytest.skip("image-only fixture and no OCR engine on PATH (spec §1d, §8 Q3)")
    floor = SCORE_SCANNED if scanned else SCORE_TEXT_LAYER
    score = eval10.fixture_score(stem)
    assert score >= floor, f"{stem}: mathspeak score {score:.3f} < {floor}"


def test_m5_gate_b_spoken_maths_mean() -> None:
    assert FORMULA_STEMS, "no formula fixtures in the manifest"
    scores: dict[str, float] = {}
    skipped: list[str] = []
    for stem in FORMULA_STEMS:
        _require_files(stem)
        if not eval10.has_text_layer(stem) and not ocr_available():
            skipped.append(stem)
            continue
        scores[stem] = eval10.fixture_score(stem)
    if skipped:
        print(f"gate (b) mean skips (no OCR engine): {skipped}")
    assert scores, "no formula fixture scored"
    mean = sum(scores.values()) / len(scores)
    detail = ", ".join(f"{k}={v:.3f}" for k, v in scores.items())
    assert mean >= SCORE_MEAN, f"mean {mean:.3f} < {SCORE_MEAN} over {len(scores)}: {detail}"


def test_m5_gate_e_profile_classes() -> None:
    from hearnarro.ingestion.profile import compute_profile  # ING-11, phase 2

    entries = [e for e in _fixtures.manifest()]
    assert len(entries) == PROFILE_TOTAL, f"{len(entries)} manifest entries, need {PROFILE_TOTAL}"
    unlabelled = [e["name"] for e in entries if e.get("profile") not in PROFILE_CLASSES]
    assert not unlabelled, f"no manifest profile: {unlabelled}"
    mismatches: list[str] = []
    skipped: list[str] = []
    for e in entries:
        name = e["name"]
        if not eval10.has_text_layer(name) and not ocr_available():
            skipped.append(name)
            continue
        result = _fixtures.ingest_result(name)
        got = compute_profile(result.pages, result.blocks).cls
        if got != e["profile"]:
            mismatches.append(f"{name}: {got} != {e['profile']}")
    if skipped:
        print(f"gate (e) skips (no OCR engine): {skipped}")
    assert len(mismatches) <= PROFILE_MAX_MISMATCH, mismatches
