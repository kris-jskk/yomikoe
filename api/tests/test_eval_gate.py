"""E0 eval gate: runner, run-record store and compare (EVAL-1, EVAL-2; D31, D32, D33).

One tier-0 run of EVAL-1 (reading order) and EVAL-2 (sentence boundaries) is written to a
temporary directory; the record must follow the shape in `_agent/specs/evals-design.md` 3.4.
`compare` must report zero deltas for a record against itself and flag exactly one example
lowered by 0.02 (tolerance 0.01, D33). Scanned fixtures are skipped without tesseract, as in
the golden test, so counts are taken over the scoreable fixtures.
"""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any

import pytest

from hearnarro.ingestion.extract import ocr_available

FIXTURES = Path(__file__).parent / "fixtures" / "pdfs"
ENTRIES: list[dict] = json.loads((FIXTURES / "manifest.json").read_text())
EVAL1_COUNT = sum(1 for e in ENTRIES if e["class"] != "scanned" or ocr_available())
EVAL2_COUNT = sum(1 for e in ENTRIES if e["class"] != "scanned")
EVAL1_CLASSES = {e["class"] for e in ENTRIES if e["class"] != "scanned" or ocr_available()}


@pytest.fixture(scope="module")
def run_result(tmp_path_factory: pytest.TempPathFactory) -> tuple[dict[str, Any], Path]:
    from hearnarro.evals.runner import run

    out = tmp_path_factory.mktemp("runs")
    record, path = run(["EVAL-1", "EVAL-2"], out_dir=out, tier=0)
    return record, path


def test_eval1_eval2_record_written_with_spec_shape(run_result: tuple[dict, Path]) -> None:
    record, path = run_result
    assert path.exists()
    assert json.loads(path.read_text()) == record
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}_[0-9a-f]{7,}", record["run_id"])
    assert path.name == f"{record['run_id']}.json"
    assert record["run_id"].endswith(record["commit"])
    assert record["date"].startswith(record["run_id"][:10])
    config = record["config"]
    assert config["backend"] == "fake"
    assert config["tesseract"] is ocr_available()
    assert isinstance(config["python"], str)
    assert set(record["suites"]) == {"EVAL-1", "EVAL-2"}
    latest = json.loads((path.parent / "latest.json").read_text())
    assert latest["run_id"] == record["run_id"]


def test_eval1_examples_and_aggregate(run_result: tuple[dict, Path]) -> None:
    suite = run_result[0]["suites"]["EVAL-1"]
    examples = suite["examples"]
    assert len(examples) == EVAL1_COUNT
    for ex in examples:
        assert {"id", "class", "score"} <= set(ex)
        assert 0.0 <= ex["score"] <= 1.0
    scores = [ex["score"] for ex in examples]
    agg = suite["aggregate"]
    assert agg["mean"] == pytest.approx(sum(scores) / len(scores))
    assert agg["min"] == pytest.approx(min(scores))
    assert set(agg["by_class"]) == EVAL1_CLASSES


def test_eval2_examples_and_aggregate(run_result: tuple[dict, Path]) -> None:
    suite = run_result[0]["suites"]["EVAL-2"]
    examples = suite["examples"]
    assert len(examples) == EVAL2_COUNT
    for ex in examples:
        assert {"id", "class", "score", "precision", "recall", "f1"} <= set(ex)
        assert ex["score"] == ex["f1"]
    agg = suite["aggregate"]
    assert agg["mean_f1"] == pytest.approx(sum(ex["f1"] for ex in examples) / len(examples))
    assert agg["min_recall"] == pytest.approx(min(ex["recall"] for ex in examples))


def test_e0_compare_identical_records_has_zero_deltas(run_result: tuple[dict, Path]) -> None:
    from hearnarro.evals.store import compare

    record = run_result[0]
    result = compare(record, copy.deepcopy(record))
    assert result["regressions"] == []
    for suite in result["suites"].values():
        assert all(d == 0 for d in suite["aggregate"].values())
        for metrics in suite["examples"].values():
            assert all(d == 0 for d in metrics.values())


def test_e0_compare_flags_one_lowered_example(run_result: tuple[dict, Path]) -> None:
    from hearnarro.evals.store import compare

    record = run_result[0]
    candidate = copy.deepcopy(record)
    target = candidate["suites"]["EVAL-1"]["examples"][0]
    target["score"] -= 0.02
    result = compare(record, candidate)
    flagged = {(r["suite"], r["id"]) for r in result["regressions"]}
    assert flagged == {("EVAL-1", target["id"])}
    assert result["suites"]["EVAL-1"]["examples"][target["id"]]["score"] == pytest.approx(-0.02)
