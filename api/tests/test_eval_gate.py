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
M1_TEXT = ("academic", "report", "tables")
EVAL2_COUNT = sum(1 for e in ENTRIES if e["class"] in M1_TEXT)
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

EVAL3_COUNT = sum(1 for e in ENTRIES if e["class"] in M1_TEXT)
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
    # EVAL-10 (M5 mathspeak) is also tier 0 now.
    assert set(all_run["suites"]) == {"EVAL-1", "EVAL-2", "EVAL-3", "EVAL-4", "EVAL-10"}
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


def _eval4_skip_reason() -> str | None:
    from hearnarro.evals.suites import eval4_speech_form

    return eval4_speech_form.unavailable()


def test_eval4_phonemes_through_backend_front_end() -> None:
    """EVAL-4 scores what the listener hears: misaki G2P with the num2words shim (D15)
    expands digits, so "12" and "twelve" give the same phonemes (EVAL-4, SYN-4)."""
    reason = _eval4_skip_reason()
    if reason:
        pytest.skip(reason)
    from hearnarro.evals.suites.eval4_speech_form import phonemes

    assert phonemes("There were 12 people.") == phonemes("There were twelve people.")
    assert not set("".join(phonemes("Yes, the F B I. Then!"))) & set(",.!")
    assert phonemes("in 1984") == phonemes("in nineteen eighty-four")


def test_eval4_examples_and_aggregate(all_run: dict[str, Any]) -> None:
    from hearnarro.evals.suites import eval4_speech_form

    suite = all_run["suites"]["EVAL-4"]
    reason = _eval4_skip_reason()
    if reason:
        assert len(suite["skipped"]) == len(eval4_speech_form.load_pairs())
        assert {s["reason"] for s in suite["skipped"]} == {reason}
        pytest.skip(reason)
    examples = suite["examples"]
    assert len(examples) == len(eval4_speech_form.load_pairs())
    from hearnarro.evals.suites.eval4_speech_form import strip_stress

    fields = {"id", "class", "exact", "exact_stress", "partial", "score", "actual"}
    fields |= {"actual_ph", "expected_ph"}
    for ex in examples:
        assert fields | {"text_exact", "text_partial"} <= set(ex)
        assert isinstance(ex["exact"], bool) and isinstance(ex["text_exact"], bool)
        assert 0.0 <= ex["partial"] <= 1.0 and 0.0 <= ex["text_partial"] <= 1.0
        assert ex["exact_stress"] == (ex["actual_ph"] == ex["expected_ph"])
        assert ex["exact"] == (strip_stress(ex["actual_ph"]) == strip_stress(ex["expected_ph"]))
        assert ex["exact"] or not ex["exact_stress"]
        assert not ex["exact"] or ex["partial"] == 1.0
        assert not ex["text_exact"] or ex["text_partial"] == 1.0
    agg = suite["aggregate"]
    n = len(examples)
    assert agg["accuracy"] == pytest.approx(sum(e["exact"] for e in examples) / n)
    assert agg["partial_mean"] == pytest.approx(sum(e["partial"] for e in examples) / n)
    assert agg["accuracy_stress"] == pytest.approx(sum(e["exact_stress"] for e in examples) / n)
    assert agg["accuracy"] >= agg["accuracy_stress"]
    assert strip_stress("ˈhɛlO ˌwɜɹld") == "hɛlO wɜɹld"
    assert agg["text_accuracy"] == pytest.approx(sum(e["text_exact"] for e in examples) / n)
    assert agg["text_partial_mean"] == pytest.approx(sum(e["text_partial"] for e in examples) / n)
    assert set(agg["by_category"]) == {e["class"] for e in examples} >= EVAL4_CATEGORIES


# --- E2: tier-1 suites with the real voice: EVAL-5 intelligibility, EVAL-6 sync, EVAL-7 speed
# (SYN-1, SYN-4, SYN-5, PLAY-3; D31, D34). Kokoro synthesizes, faster-whisper (MIT, pinned in
# settings.py) transcribes. Five sentences at speed 1.0, both eval voices.

E2_N = 5


@pytest.fixture(scope="module")
def e2_examples() -> list[dict[str, Any]]:
    from hearnarro.evals.suites import eval5_intelligibility

    reason = eval5_intelligibility.unavailable()
    if reason:
        pytest.skip(reason)
    return eval5_intelligibility.dataset(limit=E2_N, speeds=(1.0,))


@pytest.mark.model
def test_eval5_eval6_eval7_registered_tier1() -> None:
    from hearnarro.evals.suites import SUITES, direction, select

    for sid in ("EVAL-5", "EVAL-6", "EVAL-7"):
        assert SUITES[sid].TIER == 1
        assert direction(sid) == "lower"
    assert {m.ID for m in select(["all"], 0)} == {"EVAL-1", "EVAL-2", "EVAL-3", "EVAL-4"}
    assert {"EVAL-5", "EVAL-6", "EVAL-7"} <= {m.ID for m in select(["all"], 1)}


@pytest.mark.model
def test_eval5_dataset_50_sentences_two_voices() -> None:
    from hearnarro.evals.suites import eval5_intelligibility as e5
    from hearnarro.synthesis.kokoro_backend import voice_from_id

    sentences = e5.load_sentences()
    assert len(sentences) == 50 == len({s["id"] for s in sentences})
    assert e5.load_sentences() == sentences  # committed list, deterministic
    genders = {voice_from_id(v).gender for v in e5.VOICES}
    assert genders == {"female", "male"} and len(e5.VOICES) == 2
    assert {1.0, 2.0} <= set(e5.SPEEDS)
    full = e5.dataset()
    assert len(full) == 50 * len(e5.VOICES) * len(e5.SPEEDS)


@pytest.mark.model
def test_eval5_wer_normalization() -> None:
    from hearnarro.evals.suites.eval5_intelligibility import norm_words, wer

    assert norm_words("Self-driving cars, she said: \"Go!\"") == [
        "self", "driving", "cars", "she", "said", "go"
    ]  # fmt: skip
    assert wer(["a", "b", "c", "d"], ["a", "x", "c"]) == pytest.approx(0.5)
    assert wer(["a"], ["a", "b"]) == pytest.approx(1.0)


@pytest.mark.model
def test_eval5_intelligibility_round_trip(e2_examples: list[dict[str, Any]]) -> None:
    from hearnarro.evals.suites import eval5_intelligibility as e5

    assert len(e2_examples) == E2_N * len(e5.VOICES)
    scores = [e5.score(ex) for ex in e2_examples]
    for s in scores:
        assert {"id", "class", "sentence_id", "speed", "voice", "reference", "hypothesis"} <= set(s)
        assert s["direction"] == "lower" and s["score"] == s["wer"] >= 0.0
        assert s["speed"] == 1.0 and s["reference"]
    agg = e5.aggregate(scores)
    assert agg["mean_wer"] == pytest.approx(sum(s["wer"] for s in scores) / len(scores))
    assert agg["worst"]["wer"] == max(s["wer"] for s in scores)
    assert set(agg["per_voice"]) == set(e5.VOICES) and set(agg["per_speed"]) == {"1.0"}
    assert agg["mean_wer"] < 0.25  # SYN-1: the voice is intelligible at normal speed


@pytest.mark.model
def test_eval6_sync_word_offsets(e2_examples: list[dict[str, Any]]) -> None:
    from hearnarro.evals.suites import eval6_sync as e6

    scores = [e6.score(ex) for ex in e2_examples]
    for s in scores:
        assert {"id", "class", "speed", "voice", "mean_abs_offset_ms", "share_within_150ms"} <= set(
            s
        )
        assert 0 < s["n_matched"] <= s["n_backend_words"]
        assert len(s["abs_offsets_ms"]) == s["n_matched"]
        assert s["score"] == s["mean_abs_offset_ms"] >= 0.0
        assert 0.0 <= s["share_within_150ms"] <= 1.0
        assert s["n_matched"] >= 0.6 * s["n_backend_words"]
    agg = e6.aggregate(scores)
    pooled = [o for s in scores for o in s["abs_offsets_ms"]]
    assert agg["mean_abs_offset_ms"] == pytest.approx(sum(pooled) / len(pooled))
    assert agg["share_within_150ms"] == pytest.approx(sum(o <= 150 for o in pooled) / len(pooled))
    assert set(agg["per_speed"]) == {"1.0"}
    assert agg["mean_abs_offset_ms"] < 250  # PLAY-3: highlight follows the voice


@pytest.mark.model
def test_eval6_compare_rules_per_metric() -> None:
    from hearnarro.evals.store import compare

    ex = {"id": "s", "class": "1.0", "score": 100.0, "mean_abs_offset_ms": 100.0}
    ex["share_within_150ms"] = 0.8
    base = {"run_id": "a", "suites": {"EVAL-6": {"examples": [ex], "aggregate": {}}}}
    within = copy.deepcopy(base)
    within["suites"]["EVAL-6"]["examples"][0].update(score=109.0, mean_abs_offset_ms=109.0)
    within["suites"]["EVAL-6"]["examples"][0]["share_within_150ms"] = 0.9
    assert compare(base, within)["regressions"] == []  # +9 % timing, share up
    worse = copy.deepcopy(base)
    worse["suites"]["EVAL-6"]["examples"][0]["share_within_150ms"] = 0.7
    (reg,) = compare(base, worse)["regressions"]
    assert set(reg["metrics"]) == {"share_within_150ms"}


@pytest.mark.model
def test_eval7_speed_from_bench() -> None:
    from hearnarro.evals.suites import eval7_speed as e7

    full = e7.dataset()
    assert len({ex["sentence"] for ex in full}) == 20
    examples = e7.dataset(limit=E2_N, speeds=(1.0,))
    if examples[0]["skip"]:
        pytest.skip(examples[0]["skip"])
    scores = [e7.score(ex) for ex in examples]
    for s in scores:
        assert s["ttfa_ms"] > 0 and s["audio_ms"] > 0
        assert s["rtf"] == pytest.approx(s["ttfa_ms"] / s["audio_ms"], rel=1e-3)
        assert s["score"] == s["ttfa_ms"]
    agg = e7.aggregate(scores)
    assert agg["ttfa_p50_ms"] <= agg["ttfa_p95_ms"]
    assert set(agg["per_speed"]) == {"1.0"}
    assert agg["ttfa_p95_ms"] <= 2000  # PRD M2: first audio within 2 s


# --- E3: HTML scorecard (D31, D33) -------------------------------------------------------

RUNS = Path(__file__).resolve().parents[2] / "evals" / "runs"
NEWEST = RUNS / "2026-10-17_d5f2e10.json"
FIRST_BASELINE = RUNS / "2026-10-17_eadaef6.json"
# Headline aggregates of the newest record as the scorecard prints them (4 decimals below 100,
# 1 decimal from 100 up): EVAL-1 mean, EVAL-2 mean_f1, EVAL-3 total_mean_rate, EVAL-4
# accuracy, EVAL-5 mean_wer, EVAL-6 share_within_150ms, EVAL-7 ttfa_p95_ms and rtf_mean.
NEWEST_HEADLINES = ["0.9914", "0.9661", "2.5847", "0.6921", "0.3312", "0.7094", "2163.4", "0.0954"]


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def test_e3_report_html_newest_alone() -> None:
    from hearnarro.evals import report

    record = _load(NEWEST)
    html = report.html_scorecard(record)
    assert html.startswith("<title>")
    assert '<meta name="claude:viewport-fit-sides" content="cover">' in html
    assert "<!doctype" not in html.lower() and "<body" not in html
    assert "HearNarro Eval Scorecard" in html and record["run_id"] in html
    for sid in record["suites"]:
        assert f'id="{sid}"' in html, sid
    for value in NEWEST_HEADLINES:
        assert value in html, value


def test_e3_report_html_against_first_baseline_marks_no_baseline() -> None:
    from hearnarro.evals import report

    record, base = _load(NEWEST), _load(FIRST_BASELINE)
    html = report.html_scorecard(record, base)
    assert base["run_id"] in html
    missing = [sid for sid in record["suites"] if sid not in base["suites"]]
    assert missing == ["EVAL-3", "EVAL-4", "EVAL-5", "EVAL-6", "EVAL-7"]
    for sid in missing:
        tile = re.search(rf'<div class="tile[^"]*" data-suite="{sid}">(.*?)</div>', html, re.DOTALL)
        assert tile and "no baseline" in tile.group(1), sid
    for value in NEWEST_HEADLINES:
        assert value in html, value


def test_e3_report_html_regressions_block_lists_lowered_example() -> None:
    from hearnarro.evals import report

    base = _load(NEWEST)
    cand = copy.deepcopy(base)
    cand["run_id"] = "2026-10-17_synthetic"
    lowered, kept = cand["suites"]["EVAL-2"]["examples"][:2]
    lowered["score"] -= 0.05
    lowered["f1"] -= 0.05
    html = report.html_scorecard(cand, base)
    block = re.search(r'<ol class="regressions" data-suite="EVAL-2">(.*?)</ol>', html, re.DOTALL)
    assert block, "no EVAL-2 regressions block"
    assert lowered["id"] in block.group(1)
    assert kept["id"] not in block.group(1)
    assert "-0.0500" in block.group(1)


def test_e3_report_html_standalone_and_cli(tmp_path: Path) -> None:
    from hearnarro.evals import report
    from hearnarro.evals.__main__ import main

    record = _load(NEWEST)
    assert report.html_scorecard(record, standalone=True).startswith("<!doctype html>")
    out = tmp_path / "card.html"
    code = main(["report", str(NEWEST), "--baseline", str(FIRST_BASELINE), "--html", str(out)])
    assert code == 0 and out.exists()
    text = out.read_text()
    assert text.startswith("<title>") and "no baseline" in text
    out2 = tmp_path / "card_standalone.html"
    main(["report", str(NEWEST), "--html", str(out2), "--standalone"])
    assert out2.read_text().startswith("<!doctype html>")
