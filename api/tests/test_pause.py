"""SYN-1 with the real model: after the per-clip trim the pause between two sentences is the
fixed pad (tail + lead), not Kokoro's ~0.8 s of edge silence (results 369)."""

from __future__ import annotations

import functools

import numpy as np
import pytest

from hearnarro.synthesis.trim import (
    DEFAULT_LEAD_MS,
    DEFAULT_TAIL_MS,
    FIRST_WORD_GUARD_MS,
    trim_silence,
)
from tests.conftest import fifty_fixture_sentences, make_service
from tests.test_syn1_timestamps import assert_timestamp_invariants

VOICE = "af_heart"
SENTENCES = fifty_fixture_sentences()[:10]
TH = 10 ** (-40 / 20)


@functools.cache
def _backend():
    from hearnarro.synthesis.kokoro_backend import PINNED_REVISION, KokoroBackend

    return KokoroBackend(revision=PINNED_REVISION)


def _edges_ms(pcm: bytes, sr: int) -> tuple[float, float]:
    x = np.frombuffer(pcm, dtype="<i2").astype(np.float64) / 32768.0
    loud = np.flatnonzero(np.abs(x) > TH)
    return loud[0] * 1000 / sr, (len(x) - 1 - loud[-1]) * 1000 / sr


@pytest.mark.model
@pytest.mark.parametrize("speed", [1.0, 2.0])
def test_syn1_kokoro_trimmed_tail_is_the_pad(speed: float) -> None:
    for seg in SENTENCES:
        r = _backend().synthesize(seg.normalized_text, VOICE, speed)
        _, raw_tail = _edges_ms(r.audio, r.sample_rate)
        pcm, ts = trim_silence(r.audio, r.sample_rate, r.timestamps)
        lead, tail = _edges_ms(pcm, r.sample_rate)
        assert tail <= DEFAULT_TAIL_MS + 30, f"{seg.id} @ {speed}: tail {tail:.0f} ms"
        assert lead <= DEFAULT_LEAD_MS + 30, f"{seg.id} @ {speed}: lead {lead:.0f} ms"
        assert ts[0].start_ms >= FIRST_WORD_GUARD_MS, f"{seg.id} @ {speed}: {ts[0]}"
        assert len(ts) == len(r.timestamps)
        duration = int(len(pcm) // 2 * 1000 / r.sample_rate)
        prev = 0
        for t in ts:
            assert prev <= t.start_ms <= t.end_ms <= duration, t
            prev = t.end_ms
        assert raw_tail > tail or raw_tail <= DEFAULT_TAIL_MS  # it did cut when it could


@pytest.mark.model
@pytest.mark.parametrize("speed", [1.0, 2.0, 2.5])
async def test_syn1_kokoro_service_trimmed_timestamps_keep_invariants(speed: float) -> None:
    service, _, _ = make_service(_backend(), segments=SENTENCES)
    try:
        for seg in SENTENCES:
            entry = await service.get_audio(seg.id, VOICE, speed)
            assert entry.status == "ready"
            assert_timestamp_invariants(entry, seg)
            assert entry.timestamps[0].start_ms >= FIRST_WORD_GUARD_MS * 0.8  # /1.25 at 2.5
    finally:
        await service.shutdown()
