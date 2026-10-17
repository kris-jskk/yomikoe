"""Eval runner (D31, D32): score every example of the selected suites and write one record."""

from __future__ import annotations

import platform
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from hearnarro.evals import store
from hearnarro.evals.suites import select


def _short_sha() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=Path(__file__).resolve().parent,
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return "nogit"
    return out.stdout.strip()


def _config(tier: int) -> dict[str, Any]:
    from hearnarro.ingestion.extract import ocr_available

    return {
        "backend": "fake",  # tier 0 runs no TTS model
        "speed": 1.0,
        "tesseract": ocr_available(),
        "python": platform.python_version(),
        "tier": tier,
    }


def run(
    suite_ids: list[str], out_dir: Path | None = None, tier: int = 0
) -> tuple[dict[str, Any], Path]:
    """Run the suites (ids or ``all``), write the record to ``out_dir``; return (record, path).

    Every non-skipped example's score is kept; skipped examples are listed with their reason.
    """
    modules = select(suite_ids, tier)
    now = datetime.now(UTC)
    sha = _short_sha()
    record: dict[str, Any] = {
        "run_id": f"{now:%Y-%m-%d}_{sha}",
        "commit": sha,
        "date": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "config": _config(tier),
        "suites": {},
    }
    started = time.perf_counter()
    for module in modules:
        t0 = time.perf_counter()
        examples, skipped = [], []
        for ex in module.dataset():
            if ex["skip"]:
                skipped.append({"id": ex["id"], "class": ex["class"], "reason": ex["skip"]})
            else:
                examples.append(module.score(ex))
        record["suites"][module.ID] = {
            "title": module.TITLE,
            "tier": module.TIER,
            "examples": examples,
            "skipped": skipped,
            "aggregate": module.aggregate(examples),
            "seconds": round(time.perf_counter() - t0, 2),
        }
    record["seconds"] = round(time.perf_counter() - started, 2)
    path = store.write_record(record, out_dir or store.DEFAULT_RUNS_DIR)
    return record, path
