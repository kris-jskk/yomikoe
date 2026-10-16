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

# (fixture, check) -> allowed count, pinned at the count measured when the checklist was
# added (_agent/results/243_quality_fixtures_before_allowlist.txt). A higher count fails.
ALLOWED: dict[tuple[str, str], int] = {
    # Math ellipsis "x1, . . . , xd" matches the leader-dot pattern; not a TOC leader.
    ("academic_02_memduet", "leader_dots"): 1,
    ("tables_01_pfn_bayes", "leader_dots"): 3,
    ("tables_02_non_gaussian_sem", "leader_dots"): 8,
    # Suspended hyphen "16K- and 65K-token" is correct English, not a missed join.
    ("academic_03_pruned_reasoning", "dangling_hyphens"): 1,
    # Equation fragments ("!", ".", ",") and empty-text segments from math/table regions.
    ("academic_02_memduet", "punctuation_only"): 2,
    ("academic_03_pruned_reasoning", "punctuation_only"): 1,
    ("tables_01_pfn_bayes", "punctuation_only"): 1,
    ("tables_03_copula_subspaces", "punctuation_only"): 4,
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
    # NIST cover page and inner title page repeat the same title headings.
    ("report_01_zero_trust", "duplicate_runs"): 2,
    ("report_02_patch_mgmt", "duplicate_runs"): 5,
    ("report_03_ssdf", "duplicate_runs"): 3,
    ("report_04_rmf", "duplicate_runs"): 4,
    ("report_05_controls", "duplicate_runs"): 4,
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
