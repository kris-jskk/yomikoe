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


def _config(tier: int, model_tier: bool = False) -> dict[str, Any]:
    from hearnarro.ingestion.extract import ocr_available

    config: dict[str, Any] = {
        "backend": "fake",  # tier 0 runs no TTS model
        "speed": 1.0,
        "tesseract": ocr_available(),
        "python": platform.python_version(),
        "tier": tier,
    }
    if model_tier:  # tier-1 suites ran: the real voice and the recogniser (D31, D34)
        from hearnarro import settings
        from hearnarro.evals.suites import eval5_intelligibility as e5

        config.update(
            backend="kokoro",
            kokoro_revision=settings.DEFAULT_KOKORO_REVISION,
            asr_model=settings.ASR_MODEL_REPO,
            asr_revision=settings.ASR_MODEL_REVISION,
            voices=list(e5.VOICES),
            speeds=list(e5.SPEEDS),
            machine=f"{platform.platform()} {platform.machine()}",
        )
    return config


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
        "config": _config(tier, any(m.TIER >= 1 for m in modules)),
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
            "direction": getattr(module, "DIRECTION", "higher"),
            "examples": examples,
            "skipped": skipped,
            "aggregate": module.aggregate(examples),
            "seconds": round(time.perf_counter() - t0, 2),
        }
    record["seconds"] = round(time.perf_counter() - started, 2)
    path = store.write_record(record, out_dir or store.DEFAULT_RUNS_DIR)
    return record, path
