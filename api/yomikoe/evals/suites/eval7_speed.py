"""EVAL-7 Speed: how fast is synthesis on this machine? (SYN-5, PRD M2 metrics; D31)

Adopts ``scripts/bench.py`` unchanged: its sentence rule (``bench_sentences(20)``), speeds
(``SPEEDS`` 0.5/1/2/3), voice (the backend's first, as bench picks it) and measurement
(``run_one``: synthesize at the native speed, stretch above the native maximum; TTFA = wall
time of that, RTF = wall / audio). The script is loaded by path, so its CLI is untouched.
The warmed backend is the run's shared one (``_voice.backend``), so cold start is not part
of EVAL-7 (bench.py still reports it). Per example one bench row; aggregates TTFA p50/p95,
RTF mean/p50 and the share within the PRD's 2 s, overall and per speed. Lower is better.
"""

from __future__ import annotations

import importlib.util
import statistics
from functools import cache
from pathlib import Path
from types import ModuleType
from typing import Any

from yomikoe.evals.scorers import percentile
from yomikoe.evals.suites import _voice

ID = "EVAL-7"
TITLE = "Speed"
TIER = 1
DIRECTION = "lower"
N_SENTENCES = 20
BENCH = Path(__file__).resolve().parents[3] / "scripts" / "bench.py"
# D33: timings regress beyond 10 % relative; sentence length and audio length are not scores.
METRIC_RULES: dict[str, tuple[str, float, bool]] = {
    "score": ("lower", 0.10, True),
    "ttfa_ms": ("lower", 0.10, True),
    "rtf": ("lower", 0.10, True),
    "audio_ms": ("none", 0.0, False),
    "chars": ("none", 0.0, False),
    "speed": ("none", 0.0, False),
}


@cache
def bench() -> ModuleType:
    """``scripts/bench.py`` imported by path (it is a script, not a package module)."""
    spec = importlib.util.spec_from_file_location("yomikoe_bench_script", BENCH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def dataset(
    limit: int | None = None, speeds: tuple[float, ...] | None = None
) -> list[dict[str, Any]]:
    reason = _voice.unavailable()
    b = bench()
    sentences = b.bench_sentences(N_SENTENCES)[:limit]
    return [
        {"id": f"bench{i:02d}@{sp}", "class": str(sp), "sentence": s, "speed": sp, "skip": reason}
        for sp in speeds or b.SPEEDS
        for i, s in enumerate(sentences)
    ]


def score(example: dict[str, Any]) -> dict[str, Any]:
    backend = _voice.backend()
    voice = backend.voices()[0].id
    wall, audio = bench().run_one(backend, example["sentence"], voice, example["speed"])
    return {
        "id": example["id"],
        "class": example["class"],
        "speed": example["speed"],
        "voice": voice,
        "chars": len(example["sentence"]),
        "ttfa_ms": round(wall, 1),
        "audio_ms": round(audio, 1),
        "rtf": round(wall / audio, 4),
        "score": round(wall, 1),
    }


def _stats(scores: list[dict[str, Any]]) -> dict[str, float]:
    t = [s["ttfa_ms"] for s in scores]
    r = [s["rtf"] for s in scores]
    limit = bench().TTFA_LIMIT_MS
    return {
        "ttfa_p50_ms": statistics.median(t),
        "ttfa_p95_ms": percentile(t, 95),
        "rtf_mean": statistics.mean(r),
        "rtf_p50": statistics.median(r),
        "share_within_2s": sum(x <= limit for x in t) / len(t),
    }


def aggregate(scores: list[dict[str, Any]]) -> dict[str, Any]:
    if not scores:
        return {"per_speed": {}}
    by_speed: dict[str, list[dict[str, Any]]] = {}
    for s in scores:
        by_speed.setdefault(str(s["speed"]), []).append(s)
    return {
        **_stats(scores),
        "per_speed": {
            k: _stats(v) for k, v in sorted(by_speed.items(), key=lambda kv: float(kv[0]))
        },
    }
