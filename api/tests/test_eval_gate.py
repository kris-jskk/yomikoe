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


# --- E1: EVAL-3 clean-text rates and EVAL-4 speech form (D31, D32, D33) ---------------------

EVAL3_COUNT = sum(1 for e in ENTRIES if e["class"] != "scanned")
EVAL4_CATEGORIES = {
    "cardinal",
    "decimal_percent",
    "year_date",
    "time",
    "money",
    "unit",
    "ordinal",
    "phone_id_range",
    "abbreviation",
    "acronym_spelled",
    "acronym_spoken",
    "mixed_edge",
    "table_cue",
    "equation_cue",
}


@pytest.fixture(scope="module")
def all_run(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    from hearnarro.evals.runner import run

    record, _ = run(["all"], out_dir=tmp_path_factory.mktemp("runs_all"), tier=0)
    return record


def test_eval3_eval4_registered_tier0_with_direction() -> None:
    from hearnarro.evals.suites import SUITES, direction

    assert SUITES["EVAL-3"].TIER == 0 and SUITES["EVAL-4"].TIER == 0
    assert direction("EVAL-3") == "lower"
    assert direction("EVAL-4") == "higher"
    assert direction("EVAL-1") == direction("EVAL-2") == "higher"


def test_eval_all_tier0_runs_four_suites_under_60s(all_run: dict[str, Any]) -> None:
    assert set(all_run["suites"]) == {"EVAL-1", "EVAL-2", "EVAL-3", "EVAL-4"}
    assert all_run["seconds"] < 60
    assert all_run["suites"]["EVAL-3"]["direction"] == "lower"


def test_eval3_rates_per_1000_words(all_run: dict[str, Any]) -> None:
    suite = all_run["suites"]["EVAL-3"]
    examples = suite["examples"]
    assert len(examples) == EVAL3_COUNT == 15
    names = set(examples[0]["checks"])
    assert {"dangling_hyphens", "ligature_artifacts", "midsentence_breaks"} <= names
    for ex in examples:
        assert ex["words"] > 0 and set(ex["checks"]) == names
        for c in ex["checks"].values():
            assert c["rate"] == pytest.approx(c["count"] * 1000 / ex["words"])
        assert ex["total_rate"] == pytest.approx(sum(c["rate"] for c in ex["checks"].values()))
        assert ex["score"] == ex["total_rate"]
    agg = suite["aggregate"]
    for name in names:
        mean = sum(ex["checks"][name]["rate"] for ex in examples) / len(examples)
        assert agg["mean_rate"][name] == pytest.approx(mean)
    assert agg["total_mean_rate"] == pytest.approx(
        sum(ex["total_rate"] for ex in examples) / len(examples)
    )


def test_eval3_compare_treats_increase_as_regression(all_run: dict[str, Any]) -> None:
    from hearnarro.evals.store import compare

    base = {"run_id": "a", "suites": {"EVAL-3": copy.deepcopy(all_run["suites"]["EVAL-3"])}}
    worse, better = copy.deepcopy(base), copy.deepcopy(base)
    worse["run_id"], better["run_id"] = "b", "c"
    target = worse["suites"]["EVAL-3"]["examples"][0]
    target["total_rate"] += 2.0
    target["score"] += 2.0
    better["suites"]["EVAL-3"]["examples"][1]["total_rate"] = 0.0
    better["suites"]["EVAL-3"]["examples"][1]["score"] = 0.0
    assert {r["id"] for r in compare(base, worse)["regressions"]} == {target["id"]}
    assert compare(base, better)["regressions"] == []


def test_eval4_dataset_shape() -> None:
    from hearnarro.evals.suites import eval4_speech_form

    rows = eval4_speech_form.load_pairs()
    assert len(rows) >= 300
    assert len({r["id"] for r in rows}) == len(rows)
    for r in rows:
        assert {"id", "category", "text", "expected"} <= set(r)
        assert set(r) <= {"id", "category", "text", "expected", "note", "block"}
        assert r["text"].strip() and r["expected"].strip()
    by_cat: dict[str, int] = {}
    for r in rows:
        by_cat[r["category"]] = by_cat.get(r["category"], 0) + 1
    assert EVAL4_CATEGORIES <= set(by_cat)
    assert all(n >= 15 for n in by_cat.values()), by_cat


def test_eval4_spoken_uses_the_app_path() -> None:
    """Ingestion normalization (ING-6/7) then the backend's acronym decision (SYN-4)."""
    from hearnarro.evals.suites.eval4_speech_form import spoken

    assert spoken("Read the PDF from NASA.") == "Read the P D F from NASA."
    assert spoken("See shopping.com now.") == "See shopping dot com now."
    assert spoken("x = √(a² + b²)          (12)", block="equation") == "Equation 12."
    assert spoken("Name | Role\nAda | Analyst", block="table").startswith("Table 1, 2 rows.")


def test_eval4_examples_and_aggregate(all_run: dict[str, Any]) -> None:
    from hearnarro.evals.suites import eval4_speech_form

    suite = all_run["suites"]["EVAL-4"]
    examples = suite["examples"]
    assert len(examples) == len(eval4_speech_form.load_pairs())
    for ex in examples:
        assert {"id", "class", "exact", "partial", "score", "actual"} <= set(ex)
        assert isinstance(ex["exact"], bool)
        assert 0.0 <= ex["partial"] <= 1.0
        assert not ex["exact"] or ex["partial"] == 1.0
    agg = suite["aggregate"]
    assert agg["accuracy"] == pytest.approx(sum(e["exact"] for e in examples) / len(examples))
    assert agg["partial_mean"] == pytest.approx(sum(e["partial"] for e in examples) / len(examples))
    assert set(agg["by_category"]) == {e["class"] for e in examples} >= EVAL4_CATEGORIES
