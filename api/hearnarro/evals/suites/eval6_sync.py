"""EVAL-6 Sync: do the backend's word timestamps match the audio? (SYN-1, PLAY-3; D31, D34)

Same examples as EVAL-5 (sentence × voice × speed) and the same cached round trip
(``_voice.roundtrip``), so each clip is synthesized and transcribed once per run. The
recogniser's words and the backend's ``WordTimestamp`` words are normalized like EVAL-5
(``norm_words``; a hyphenated word's later pieces carry no start time) and aligned with the
word edit script (``scorers.matched_pairs``); only pairs whose words are equal count. Per
example: ``mean_abs_offset_ms`` of word starts (lower is better), ``share_within_150ms``
(higher is better), ``n_matched`` and ``n_backend_words``. Aggregates pool every matched word
(overall, per speed, per voice) and add the p95 offset.
"""

from __future__ import annotations

from typing import Any

from hearnarro.evals.scorers import matched_pairs, percentile
from hearnarro.evals.suites import _voice
from hearnarro.evals.suites.eval5_intelligibility import dataset, norm_words, unavailable

ID = "EVAL-6"
TITLE = "Sync"
TIER = 1
DIRECTION = "lower"
WITHIN_MS = 150
# D33: offsets are timings (10 % relative); the share and the match count improve upwards.
METRIC_RULES: dict[str, tuple[str, float, bool]] = {
    "score": ("lower", 0.10, True),
    "mean_abs_offset_ms": ("lower", 0.10, True),
    "p95_abs_offset_ms": ("lower", 0.10, True),
    "share_within_150ms": ("higher", 0.01, False),
    "n_matched": ("higher", 1.0, False),
    "n_backend_words": ("none", 0.0, False),
    "speed": ("none", 0.0, False),
}

__all__ = ["DIRECTION", "ID", "TIER", "TITLE", "aggregate", "dataset", "score", "unavailable"]


def _timed(items: list[tuple[str, float]]) -> tuple[list[str], list[float | None]]:
    """Normalized words and their start times; a split word's later pieces get None."""
    out_w: list[str] = []
    out_t: list[float | None] = []
    for raw, start in items:
        for k, piece in enumerate(norm_words(raw)):
            out_w.append(piece)
            out_t.append(start if k == 0 else None)
    return out_w, out_t


def score(example: dict[str, Any]) -> dict[str, Any]:
    rt = _voice.roundtrip(example["text"], example["voice"], example["speed"])
    b_words, b_times = _timed([(t.word, float(t.start_ms)) for t in rt.timestamps])
    a_words, a_times = _timed([(w.word, w.start_ms) for w in rt.asr])
    offsets = []
    for i, j in matched_pairs(a_words, b_words):
        if a_times[i] is not None and b_times[j] is not None:
            offsets.append(round(abs(a_times[i] - b_times[j]), 1))
    mean = sum(offsets) / len(offsets) if offsets else 0.0
    return {
        "id": example["id"],
        "class": example["class"],
        "sentence_id": example["sentence_id"],
        "speed": example["speed"],
        "voice": example["voice"],
        "mean_abs_offset_ms": mean,
        "share_within_150ms": (sum(o <= WITHIN_MS for o in offsets) / len(offsets))
        if offsets
        else 0.0,
        "n_matched": len(offsets),
        "n_backend_words": sum(t is not None for t in b_times),
        "abs_offsets_ms": offsets,
        "score": mean,
    }


def _pool(scores: list[dict[str, Any]]) -> dict[str, float]:
    offs = [o for s in scores for o in s["abs_offsets_ms"]]
    n_b = sum(s["n_backend_words"] for s in scores)
    return {
        "mean_abs_offset_ms": sum(offs) / len(offs) if offs else 0.0,
        "p95_abs_offset_ms": percentile(offs, 95) if offs else 0.0,
        "share_within_150ms": sum(o <= WITHIN_MS for o in offs) / len(offs) if offs else 0.0,
        "n_matched": len(offs),
        "match_rate": len(offs) / n_b if n_b else 0.0,
    }


def aggregate(scores: list[dict[str, Any]]) -> dict[str, Any]:
    """Pooled over every matched word: overall, per speed and per voice."""
    by_speed: dict[str, list[dict[str, Any]]] = {}
    by_voice: dict[str, list[dict[str, Any]]] = {}
    for s in scores:
        by_speed.setdefault(str(s["speed"]), []).append(s)
        by_voice.setdefault(s["voice"], []).append(s)
    return {
        **_pool(scores),
        "per_speed": {
            k: _pool(v) for k, v in sorted(by_speed.items(), key=lambda kv: float(kv[0]))
        },
        "per_voice": {k: _pool(v) for k, v in sorted(by_voice.items())},
    }
