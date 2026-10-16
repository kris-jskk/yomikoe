"""Document quality checklist over the 15 text fixtures (regression gate, ING-1..ING-6).

Every thresholded check must pass on every non-scanned fixture. ``ALLOWED`` raises a
check's count threshold for one fixture; each entry says why.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hearnarro.quality import check_pdf

FIXTURES = Path(__file__).parent / "fixtures" / "pdfs"
TEXT_FIXTURES = [
    e["name"]
    for e in json.loads((FIXTURES / "manifest.json").read_text())
    if e["class"] != "scanned"
]

# (fixture, check) -> allowed count, re-pinned after the false-positive fixes (math ellipsis,
# URL "#", suspended hyphen) and with duplicate_runs / punctuation_only informational
# (_agent/results/246_allowed.txt). A higher count fails.
ALLOWED: dict[tuple[str, str], int] = {
    # A math symbol "H" set as its own line.
    ("tables_04_markov_kernel", "single_letter_segments"): 1,
    # Known splits: wrapped reference entries, inline math "PA (i)", subfigure labels,
    # and some body sentences split across blocks (open parser issue, not fixed here).
    ("academic_01_seahelm_audio", "midsentence_breaks"): 2,
    ("academic_02_memduet", "midsentence_breaks"): 2,
    ("academic_04_legislative_xml", "midsentence_breaks"): 2,
    ("tables_01_pfn_bayes", "midsentence_breaks"): 9,
    ("tables_02_non_gaussian_sem", "midsentence_breaks"): 13,
    ("tables_04_markov_kernel", "midsentence_breaks"): 6,
    ("tables_05_decomposing_learner", "midsentence_breaks"): 2,
}


def test_quality_fixture_count() -> None:
    assert len(TEXT_FIXTURES) == 15


@pytest.mark.parametrize("name", TEXT_FIXTURES)
def test_quality_fixture(name: str) -> None:
    report = check_pdf(FIXTURES / f"{name}.pdf", ocr=False)
    failing = [
        c for c in report.checks if not c.passed and c.count > ALLOWED.get((name, c.name), -1)
    ]
    assert not failing, report.table()
