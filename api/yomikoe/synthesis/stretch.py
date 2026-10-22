"""Time-stretch for speeds above the backend's native range (D6 as amended by D17, SYN-3).

The service synthesizes at the native maximum and stretches by
``ratio = requested / native_max`` (1.0 < ratio <= 1.5), then scales every timestamp by
``1 / ratio``. Implementation: an in-process numpy WSOLA (waveform-similarity overlap-add):
Hann frames of 1024 samples, synthesis hop 512, analysis hop ``512 * ratio``, and each
frame's start is moved within +-256 samples to the position that best continues the
previous frame (cross-correlation). Pitch is preserved; no extra dependency (D17).
"""

from __future__ import annotations

import dataclasses
import math

import numpy as np

from yomikoe.synthesis.backend import WordTimestamp

MAX_RATIO = 1.5
FRAME = 1024
SYN_HOP = FRAME // 2
TOLERANCE = 256


def _check_ratio(ratio: float) -> None:
    if not 1.0 < ratio <= MAX_RATIO + 1e-9:
        raise ValueError(f"stretch ratio {ratio} outside (1.0, {MAX_RATIO}]")


def stretch_pcm(pcm: bytes, sample_rate: int, ratio: float) -> bytes:
    """PCM16 mono in, PCM16 mono out, ``len(out) ≈ len(pcm) / ratio``; pitch preserved."""
    _check_ratio(ratio)
    if len(pcm) % 2:
        raise ValueError("PCM16 buffer has an odd number of bytes")
    x = np.frombuffer(pcm, dtype="<i2").astype(np.float64)
    n = len(x)
    out_len = round(n / ratio)
    if n < FRAME:  # too short to overlap-add: keep the head (< 43 ms at 24 kHz)
        return x[:out_len].astype("<i2").tobytes()

    window = np.hanning(FRAME + 1)[:FRAME]  # periodic Hann: sums to 1 at hop FRAME/2
    pad_tail = FRAME * 2 + TOLERANCE * 2
    xp = np.concatenate([np.zeros(TOLERANCE), x, np.zeros(pad_tail)])
    out = np.zeros(out_len + FRAME)
    norm = np.zeros(out_len + FRAME)
    ana_hop = SYN_HOP * ratio
    prev_in = -1
    k = 0
    while k * SYN_HOP < out_len:
        nominal = TOLERANCE + round(k * ana_hop)
        if prev_in < 0:
            start = nominal
        else:
            template = xp[prev_in + SYN_HOP : prev_in + SYN_HOP + FRAME]
            region = xp[nominal - TOLERANCE : nominal + TOLERANCE + FRAME]
            if not template.any() or not region.any():
                start = nominal
            else:
                corr = np.correlate(region, template, mode="valid")
                start = nominal - TOLERANCE + int(np.argmax(corr))
        pos = k * SYN_HOP
        out[pos : pos + FRAME] += xp[start : start + FRAME] * window
        norm[pos : pos + FRAME] += window
        prev_in = start
        k += 1
    norm[norm < 1e-3] = 1.0
    y = np.clip(np.round(out[:out_len] / norm[:out_len]), -32768, 32767)
    return y.astype("<i2").tobytes()


def scale_timestamps(ts: list[WordTimestamp], ratio: float) -> list[WordTimestamp]:
    """start_ms and end_ms times ``1 / ratio`` as ints; order and char offsets unchanged.

    Floors (with a tiny epsilon against float error), so the result is monotonic and never
    later than the exact value: each time is within 1 ms of ``t / ratio``.
    """

    def scale(ms: int) -> int:
        return math.floor(ms / ratio + 1e-9)

    return [dataclasses.replace(t, start_ms=scale(t.start_ms), end_ms=scale(t.end_ms)) for t in ts]
