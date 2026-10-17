"""Tests for usage_from_transcripts.py: cost math, totals, supervisor rows."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import usage_from_transcripts as u

SCRIPT = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "usage_from_transcripts.py"
)

# One synthetic usage record: 1M of each class, no cache_creation breakdown (=> 5m writes).
MILLION = {
    "input_tokens": 1_000_000,
    "output_tokens": 1_000_000,
    "cache_creation_input_tokens": 1_000_000,
    "cache_read_input_tokens": 1_000_000,
}


@pytest.mark.parametrize(
    "model,expected",
    [
        ("claude-fable-5-1", 10 + 12.5 + 0.25 + 50),
        ("claude-opus-5-5", 4 + 5 + 0.20 + 20),
        ("claude-sonnet-5-5", 2 + 2.5 + 0.10 + 10),
        # prompt is 3M tokens, so Haiku's over-100k tier applies
        ("claude-haiku-5-5", 0.50 + 0.625 + 0.05 + 2.50),
    ],
)
def test_cost_per_model(model: str, expected: float) -> None:
    cost, flag = u.call_cost(model, MILLION)
    assert sum(cost.values()) == pytest.approx(expected)
    assert flag == ""


def test_haiku_small_prompt_tier() -> None:
    rec = {
        "input_tokens": 50_000,
        "output_tokens": 1_000_000,
        "cache_creation_input_tokens": 0,
        "cache_read_input_tokens": 0,
    }
    cost, _ = u.call_cost("claude-haiku-5-5", rec)
    assert sum(cost.values()) == pytest.approx(50_000 * 0.10 / 1e6 + 0.50)


def test_one_hour_cache_writes_use_1h_rate() -> None:
    rec = {
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_creation_input_tokens": 1_000_000,
        "cache_creation": {
            "ephemeral_1h_input_tokens": 1_000_000,
            "ephemeral_5m_input_tokens": 0,
        },
        "cache_read_input_tokens": 0,
    }
    cost, _ = u.call_cost("claude-fable-5-1", rec)
    assert cost["cache_write_1h"] == pytest.approx(20.0)
    assert cost["cache_write_5m"] == 0


def test_unknown_model_falls_back_to_opus_and_is_flagged() -> None:
    cost, flag = u.call_cost("claude-mystery-9", MILLION)
    assert sum(cost.values()) == pytest.approx(29.20)
    assert "fallback claude-opus-5-5" in flag


def _line(kind: str, **kw) -> str:
    return (
        json.dumps(
            dict(type=kind, timestamp=kw.pop("ts", "2026-10-17T00:00:00Z"), **kw)
        )
        + "\n"
    )


def _assistant(mid: str, model: str, usage: dict, tool: str | None = None, **kw) -> str:
    content = (
        [{"type": "tool_use", "id": tool, "name": "Bash", "input": {}}]
        if tool
        else [{"type": "text", "text": "x"}]
    )
    return _line(
        "assistant",
        message={"id": mid, "model": model, "usage": usage, "content": content},
        **kw,
    )


def _usage(i: int, o: int, cc: int, cr: int) -> dict:
    return {
        "input_tokens": i,
        "output_tokens": o,
        "cache_creation_input_tokens": cc,
        "cache_read_input_tokens": cr,
    }


@pytest.fixture
def fixture_dirs(tmp_path):
    tasks = tmp_path / "sess1" / "tasks"
    tasks.mkdir(parents=True)
    a = tasks / "agentA.output"
    a.write_text(
        _line("user", message={"content": "TASK m1-alpha\nMODEL opus\nbrief text"})
        # msg1 is split over two lines (text + tool_use); the second line has the final output count
        + _assistant("msg1", "claude-opus-5-5", _usage(10, 5, 1000, 0))
        + _assistant("msg1", "claude-opus-5-5", _usage(10, 100, 1000, 0), tool="t1")
        + _assistant(
            "msg2",
            "claude-opus-5-5",
            _usage(20, 200, 0, 1000),
            tool="t2",
            ts="2026-10-17T00:05:00Z",
        )
    )
    b = tasks / "agentB.output"
    b.write_text(
        _line("user", message={"content": "TASK m2-beta\nMODEL sonnet"})
        + _assistant(
            "m1", "claude-sonnet-5-5", _usage(100, 1000, 2000, 3000), tool="t9"
        )
    )
    sessions = tmp_path / "projects"
    sessions.mkdir()
    s = sessions / "sess1.jsonl"
    s.write_text(
        _line("user", message={"content": "Start M1"})
        + _assistant("s1", "claude-fable-5-1", _usage(1, 10, 5000, 0))
        + _assistant("s1", "claude-fable-5-1", _usage(1, 50, 5000, 0))
        + _assistant("s2", "claude-fable-5-1", _usage(2, 20, 100, 5000))
        # a sidechain line is a subagent's, not the supervisor's
        + _assistant(
            "side", "claude-fable-5-1", _usage(999, 999, 999, 999), isSidechain=True
        )
    )
    return tasks, sessions


def _expected(model: str, *usages: dict) -> float:
    return sum(sum(u.call_cost(model, x)[0].values()) for x in usages)


def test_task_rows_dedupe_calls(fixture_dirs) -> None:
    tasks, _ = fixture_dirs
    r = u.summarize(str(tasks / "agentA.output"))
    assert (
        r["task"] == "m1-alpha"
        and r["brief_model"] == "opus"
        and r["session"] == "sess1"
    )
    assert r["assistant_turns"] == 2 and r["tool_calls"] == 2
    assert r["tokens"]["output"] == 300 and r["tokens"]["cache_create"] == 1000
    assert r["final_prompt"] == 1020
    assert r["cost"] == pytest.approx(
        _expected("claude-opus-5-5", _usage(10, 100, 1000, 0), _usage(20, 200, 0, 1000))
    )


def test_supervisor_row_from_jsonl(fixture_dirs) -> None:
    _, sessions = fixture_dirs
    r = u.summarize(str(sessions / "sess1.jsonl"), "supervisor")
    assert (
        r["task"] == "supervisor (session sess1)" and r["agent"] == "supervisor:sess1"
    )
    assert r["model_observed"] == "claude-fable-5-1" and r["session"] == "sess1"
    assert r["assistant_turns"] == 2
    assert r["tokens"]["output"] == 70 and r["tokens"]["cache_read"] == 5000
    assert r["cost"] == pytest.approx(
        _expected("claude-fable-5-1", _usage(1, 50, 5000, 0), _usage(2, 20, 100, 5000))
    )


def test_two_transcripts_and_supervisor_totals(fixture_dirs, tmp_path) -> None:
    tasks, sessions = fixture_dirs
    out = tmp_path / "ledger.md"
    subprocess.run(
        [
            sys.executable,
            SCRIPT,
            "--transcripts",
            str(tasks / "*.output"),
            "--sessions",
            str(sessions / "*.jsonl"),
            "--out",
            str(out),
        ],
        check=True,
        capture_output=True,
    )
    md = out.read_text()
    a = _expected("claude-opus-5-5", _usage(10, 100, 1000, 0), _usage(20, 200, 0, 1000))
    b = _expected("claude-sonnet-5-5", _usage(100, 1000, 2000, 3000))
    s = _expected("claude-fable-5-1", _usage(1, 50, 5000, 0), _usage(2, 20, 100, 5000))
    total = re.search(r"\| project total \| 3 \| ([\d,]+) \|.*\| ([\d.,]+) \|\n", md)
    assert total, md
    assert int(total.group(1).replace(",", "")) == 10 + 20 + 100 + 1 + 2
    assert float(total.group(2)) == pytest.approx(round(a + b + s, 2), abs=0.006)
    assert "| session sess1 | 3 |" in md
    assert "| m1 | 1 |" in md and "| m2 | 1 |" in md and "| supervisor | 1 |" in md
    assert "## Cost review" in md and "### Levers" in md
    assert u.RATES_SOURCE in md


def test_transcripts_mode_reads_no_sessions_by_default(fixture_dirs, tmp_path) -> None:
    tasks, _ = fixture_dirs
    out = tmp_path / "ledger.md"
    subprocess.run(
        [
            sys.executable,
            SCRIPT,
            "--transcripts",
            str(tasks / "*.output"),
            "--out",
            str(out),
        ],
        check=True,
        capture_output=True,
    )
    assert "supervisor (session" not in out.read_text().split("## Totals")[0]
