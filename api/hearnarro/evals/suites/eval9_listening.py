"""EVAL-9 Listening: does it sound good to a person? (SYN-1; D31, D34)

Tier 2 (a human session). Dataset: every session record ``evals/listening/*.json`` written by
``hearnarro.evals.listening.ingest`` from a filled rubric sheet (``data/listening_rubric.md``);
one example per rated clip. Pending sheets under ``evals/listening/pending_*/`` are not
sessions. With no session the suite records one skipped example with the reason.

Score: the rows pass through (naturalness 1..5 and pacing 1..5, higher is better;
pron_errors counted, lower is better). Aggregate: mean naturalness, mean pacing, and
pronunciation errors per 100 words, overall and per voice, plus ``n_sessions``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ID = "EVAL-9"
TITLE = "Listening"
TIER = 2
DIRECTION = "higher"
# D33: errors rise when worse; the word count is context. Ratings use the suite default.
METRIC_RULES: dict[str, tuple[str, float, bool]] = {
    "pron_errors": ("lower", 0.0, False),
    "words": ("none", 0.0, False),
}
# Repo-root evals/listening/ (suites/eval9_listening.py -> parents[4] is the repo root).
LISTENING_DIR = Path(__file__).resolve().parents[4] / "evals" / "listening"
NO_SESSIONS = "no listening sessions under evals/listening/"


def dataset(sessions_dir: Path | None = None) -> list[dict[str, Any]]:
    """One example per row of every session file; one skipped example when there are none."""
    files = sorted((sessions_dir or LISTENING_DIR).glob("*.json"))
    out: list[dict[str, Any]] = []
    for f in files:
        session = json.loads(f.read_text(encoding="utf-8"))
        sid = session.get("session_id", f.stem)
        for row in session["rows"]:
            out.append({**row, "id": f"{sid}/{row['clip']}", "class": row["voice"], "session": sid})
            out[-1]["skip"] = None
    return out or [{"id": "listening", "class": "none", "skip": NO_SESSIONS}]


def score(example: dict[str, Any]) -> dict[str, Any]:
    keys = ("id", "class", "session", "clip", "voice", "words", "naturalness", "pacing")
    return {
        **{k: example[k] for k in keys},
        "pron_errors": example["pron_errors"],
        "notes": example.get("notes", ""),
        "score": example["naturalness"],
    }


def _summary(rows: list[dict[str, Any]]) -> dict[str, float]:
    n = len(rows)
    words = sum(r["words"] for r in rows)
    return {
        "mean_naturalness": sum(r["naturalness"] for r in rows) / n if n else 0.0,
        "mean_pacing": sum(r["pacing"] for r in rows) / n if n else 0.0,
        "errors_per_100_words": 100 * sum(r["pron_errors"] for r in rows) / words if words else 0.0,
    }


def aggregate(scores: list[dict[str, Any]]) -> dict[str, Any]:
    by_voice: dict[str, list[dict[str, Any]]] = {}
    for s in scores:
        by_voice.setdefault(s["voice"], []).append(s)
    return {
        **_summary(scores),
        "per_voice": {v: _summary(rs) for v, rs in sorted(by_voice.items())},
        "n_sessions": len({s["session"] for s in scores}),
    }
