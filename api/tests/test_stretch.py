"""SYN-3 / D17: the numpy WSOLA stretch keeps length within 2 % and pitch, and
``scale_timestamps`` keeps order (unit tests for ``yomikoe.synthesis.stretch``)."""

from __future__ import annotations

import itertools

import numpy as np
import pytest

from yomikoe.synthesis.backend import WordTimestamp
from yomikoe.synthesis.stretch import scale_timestamps, stretch_pcm

SR = 24_000


def chirpy_voice(seconds: float, f0: float = 180.0) -> bytes:
    """Harmonic tone with a slow amplitude envelope (speech-like enough for WSOLA)."""
    t = np.arange(int(SR * seconds)) / SR
    env = 0.5 + 0.5 * np.sin(2 * np.pi * 3 * t) ** 2
    sig = sum(np.sin(2 * np.pi * f0 * h * t) / h for h in (1, 2, 3))
    return (6000 * env * sig).astype("<i2").tobytes()


def dominant_hz(pcm: bytes) -> float:
    x = np.frombuffer(pcm, dtype="<i2").astype(np.float64)
    spec = np.abs(np.fft.rfft(x * np.hanning(len(x))))
    return float(np.fft.rfftfreq(len(x), 1 / SR)[int(np.argmax(spec))])


@pytest.mark.parametrize("ratio", [1.05, 1.1, 1.25, 1.4, 1.5])
def test_syn3_wsola_length_within_2_percent_and_pitch_kept(ratio: float) -> None:
    pcm = chirpy_voice(1.5)
    out = stretch_pcm(pcm, SR, ratio)
    expected = len(pcm) / ratio
    assert abs(len(out) - expected) <= 0.02 * expected
    assert abs(dominant_hz(out) - dominant_hz(pcm)) <= 3.0  # pitch preserved, not resampled


def test_syn3_wsola_short_and_empty_input() -> None:
    assert stretch_pcm(b"", SR, 1.25) == b""
    short = chirpy_voice(0.02)  # under one frame
    out = stretch_pcm(short, SR, 1.25)
    assert len(out) % 2 == 0 and abs(len(out) / 2 - len(short) / 2 / 1.25) <= 1
    with pytest.raises(ValueError):
        stretch_pcm(b"\x00", SR, 1.25)


def test_syn3_scale_timestamps_keeps_order_and_offsets() -> None:
    ts = [WordTimestamp(f"w{i}", i * 97, i * 97 + 90, i * 3, i * 3 + 2) for i in range(200)]
    for ratio in (1.05, 1.17, 1.333, 1.5):
        out = scale_timestamps(ts, ratio)
        for a, b in itertools.pairwise(out):
            assert a.start_ms <= a.end_ms <= b.start_ms
        assert [(t.char_start, t.char_end) for t in out] == [(t.char_start, t.char_end) for t in ts]
