"""Gate for eval phase E4 (D31, D34): EVAL-9 Listening sheet prepare/ingest and the EVAL-8 OCR
suite (ING-2), which records a skip with its reason while tesseract is absent.

Spec: ``_agent/specs/evals-design.md`` section 3.3 (rows EVAL-8, EVAL-9) and section 4 (E4).
"""

from __future__ import annotations

from pathlib import Path

import pytest

FIXTURE_SHEET = Path(__file__).parent / "fixtures" / "listening" / "sample_sheet.md"


# ---------------------------------------------------------------------------------------
# EVAL-9 Listening
# ---------------------------------------------------------------------------------------


def test_eval9_prepare_fake_backend_writes_20_clips_and_sheet(tmp_path: Path) -> None:
    from hearnarro.evals.__main__ import main
    from hearnarro.evals.listening import parse_sheet

    out = tmp_path / "pending"
    assert main(["listening", "prepare", "--out", str(out), "--backend", "fake"]) == 0
    clips = sorted(out.glob("*.wav"))
    assert len(clips) == 20
    assert {c.name.rsplit("__", 1)[1] for c in clips} == {"af_heart.wav", "am_michael.wav"}
    header, rows = parse_sheet(out / "sheet.md")
    assert header["backend"] == "fake"
    assert header["listener"] == ""
    assert header["date"] and header["commit"]
    assert sorted(r["clip"] for r in rows) == [c.name for c in clips]
    assert all(r["naturalness"] == r["pacing"] == r["pron_errors"] == "" for r in rows)
    assert all(r["sentence"] for r in rows)


def test_eval9_ingest_sample_sheet_aggregates(tmp_path: Path) -> None:
    from hearnarro.evals.listening import ingest
    from hearnarro.evals.suites import eval9_listening as e9

    session, path = ingest(FIXTURE_SHEET, out_dir=tmp_path)
    assert path == tmp_path / "2026-10-17_fixture.json"
    assert path.is_file()
    agg = session["aggregates"]
    assert agg["per_voice"]["af_heart"] == {
        "mean_naturalness": 4.5,
        "mean_pacing": 3.5,
        "pron_errors": 1,
    }
    assert agg["per_voice"]["am_michael"] == {
        "mean_naturalness": 3.5,
        "mean_pacing": 4.5,
        "pron_errors": 3,
    }
    assert agg["overall"] == {"mean_naturalness": 4.0, "mean_pacing": 4.0, "pron_errors": 4}

    # The suite reads the session back from the directory it was written to.
    examples = e9.dataset(tmp_path)
    assert len(examples) == 4 and not any(ex["skip"] for ex in examples)
    suite_agg = e9.aggregate([e9.score(ex) for ex in examples])
    assert suite_agg["n_sessions"] == 1
    assert suite_agg["mean_naturalness"] == 4.0
    assert suite_agg["per_voice"]["am_michael"]["mean_pacing"] == 4.5
    words = sum(r["words"] for r in session["rows"])
    assert suite_agg["errors_per_100_words"] == pytest.approx(100 * 4 / words)


def test_eval9_no_sessions_is_skipped(tmp_path: Path) -> None:
    from hearnarro.evals.suites import eval9_listening as e9

    examples = e9.dataset(tmp_path)
    assert [ex["skip"] for ex in examples] == ["no listening sessions under evals/listening/"]


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("| 4 | 4 | 1 |", "|  | 4 | 1 |"),  # blank naturalness
        ("| 4 | 4 | 1 |", "| 6 | 4 | 1 |"),  # out of range
        ("| 4 | 4 | 1 |", "| 4 | 0 | 1 |"),  # pacing below 1
        ("| 4 | 4 | 1 |", "| 4 | 4 | -1 |"),  # negative errors
        ("| 4 | 4 | 1 |", "| 4 | 4.5 | 1 |"),  # not an int
        ("- listener: fixture", "- listener: "),  # blank listener
    ],
)
def test_eval9_ingest_rejects_blank_or_out_of_range(tmp_path: Path, old: str, new: str) -> None:
    from hearnarro.evals.listening import ingest

    text = FIXTURE_SHEET.read_text(encoding="utf-8")
    assert old in text
    bad = tmp_path / "bad.md"
    bad.write_text(text.replace(old, new, 1), encoding="utf-8")
    with pytest.raises(ValueError):
        ingest(bad, out_dir=tmp_path / "out")
    assert not (tmp_path / "out").exists() or not list((tmp_path / "out").iterdir())


# ---------------------------------------------------------------------------------------
# EVAL-8 OCR (ING-2)
# ---------------------------------------------------------------------------------------


def test_eval8_cer_scorer() -> None:
    from hearnarro.evals.scorers import char_error_rate

    assert char_error_rate("abcdefghij", "abcdefghij") == 0.0
    assert char_error_rate("abcdefghiX", "abcdefghij") == pytest.approx(0.1)
    assert char_error_rate("abcdefghi", "abcdefghij") == pytest.approx(0.1)  # one deletion
    assert char_error_rate("", "") == 0.0
    assert char_error_rate("abc", "") == 1.0  # empty expected: any output is all error


def test_eval8_skips_without_tesseract(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Forces ``ocr_available()`` false, so it runs the same with or without tesseract."""
    import hearnarro.ingestion.extract as extract
    from hearnarro.evals.runner import run
    from hearnarro.evals.suites import SUITES, select

    monkeypatch.setattr(extract, "ocr_available", lambda: False)
    e8 = SUITES["EVAL-8"]
    assert (e8.TIER, e8.DIRECTION) == (1, "lower")
    assert SUITES["EVAL-9"].TIER == 2
    assert {"EVAL-8", "EVAL-9"} <= {m.ID for m in select(["all"], 2)}
    record, _ = run(["EVAL-8"], out_dir=tmp_path, tier=1)
    suite = record["suites"]["EVAL-8"]
    assert suite["examples"] == []
    assert len(suite["skipped"]) == 5
    assert all(s["class"] == "scanned" for s in suite["skipped"])
    assert {s["reason"] for s in suite["skipped"]} == {"OCR unavailable (tesseract)"}
