"""Per-clip silence trim to a fixed pad (SYN-1; Technical Design "Synthesis service").

Kokoro wraps every sentence in ~300 ms of leading and ~470 ms of trailing near-silence at
1.0x (results 369); played back to back that is a ~0.8 s pause after every sentence. The
service trims each clip right after the backend returns and before any stretch, so the gap
between two sentences is ``tail_ms + lead_ms`` at every speed (divided by the stretch
ratio above the native range).
"""

from __future__ import annotations

import dataclasses

import numpy as np

from yomikoe.synthesis.backend import WordTimestamp

DEFAULT_LEAD_MS = 60
DEFAULT_TAIL_MS = 150
DEFAULT_THRESHOLD_DBFS = -40.0
FIRST_WORD_GUARD_MS = 20  # never cut closer than this to the first word's start_ms


def trim_silence(
    pcm: bytes,
    sample_rate: int,
    timestamps: list[WordTimestamp],
    *,
    lead_ms: int = DEFAULT_LEAD_MS,
    tail_ms: int = DEFAULT_TAIL_MS,
    threshold_dbfs: float = DEFAULT_THRESHOLD_DBFS,
) -> tuple[bytes, list[WordTimestamp]]:
    """PCM16 mono in; leading silence cut to ``lead_ms`` and trailing silence to ``tail_ms``.

    Silence is every sample at or below ``threshold_dbfs``; no sample above it is removed.
    The head cut is whole milliseconds and stops ``FIRST_WORD_GUARD_MS`` before the first
    word's ``start_ms``. Every timestamp moves earlier by the head cut, and ``start_ms`` /
    ``end_ms`` are clamped to the new duration. A clip with no sample above the threshold
    (or empty) is returned unchanged; so is one whose silences already fit the pads.
    """
    x = np.frombuffer(pcm[: len(pcm) - len(pcm) % 2], dtype="<i2")
    limit = 32768.0 * 10 ** (threshold_dbfs / 20)
    loud = np.flatnonzero(np.abs(x.astype(np.int32)) > limit)
    if len(loud) == 0:
        return pcm, timestamps

    head_samples = max(0, int(loud[0]) - lead_ms * sample_rate // 1000)
    head_ms = head_samples * 1000 // sample_rate
    if timestamps:
        head_ms = min(head_ms, max(0, timestamps[0].start_ms - FIRST_WORD_GUARD_MS))
    head = head_ms * sample_rate // 1000
    end = min(len(x), int(loud[-1]) + 1 + tail_ms * sample_rate // 1000)
    if head == 0 and end == len(x):
        return pcm, timestamps

    out = x[head:end].tobytes()
    duration_ms = int((end - head) * 1000 / sample_rate)
    shifted = []
    for t in timestamps:
        start = min(max(t.start_ms - head_ms, 0), duration_ms)
        stop = min(max(t.end_ms - head_ms, start), duration_ms)
        shifted.append(dataclasses.replace(t, start_ms=start, end_ms=stop))
    return out, shifted
