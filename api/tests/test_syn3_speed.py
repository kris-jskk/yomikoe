"""SYN-3 speed: native path up to the backend's max, synthesize-at-max + stretch above it
(D6), ``scale_timestamps`` math, and the API's 0.5..3.0 in 0.05 steps validation."""

from __future__ import annotations

import math
import struct
from pathlib import Path

import pytest

from hearnarro.synthesis.backend import WordTimestamp
from hearnarro.synthesis.encode import WavEncoder
from hearnarro.synthesis.fake import FakeBackend
from tests.conftest import fifty_fixture_sentences, make_service

SR = 24_000
VOICE = "fake_m1"


def tone(seconds: float) -> bytes:
    n = int(SR * seconds)
    return b"".join(
        struct.pack("<h", int(8000 * math.sin(2 * math.pi * 220 * i / SR))) for i in range(n)
    )


# --- scale_timestamps ---------------------------------------------------------------------


def test_syn3_scale_timestamps_math() -> None:
    from hearnarro.synthesis.stretch import scale_timestamps

    ts = [
        WordTimestamp("Zero", 0, 300, 0, 4),
        WordTimestamp("trust", 300, 750, 5, 10),
        WordTimestamp("now.", 750, 1500, 11, 15),
    ]
    out = scale_timestamps(ts, 1.5)
    assert [(t.start_ms, t.end_ms) for t in out] == [(0, 200), (200, 500), (500, 1000)]
    assert [(t.word, t.char_start, t.char_end) for t in out] == [
        (t.word, t.char_start, t.char_end) for t in ts
    ]
    assert all(isinstance(t.start_ms, int) and isinstance(t.end_ms, int) for t in out)
    assert scale_timestamps([], 1.2) == []


@pytest.mark.parametrize("ratio", [1.05, 1.1, 1.25, 1.333, 1.5])
def test_syn3_scale_timestamps_within_one_ms_of_exact(ratio: float) -> None:
    from hearnarro.synthesis.stretch import scale_timestamps

    ts = FakeBackend().synthesize(fifty_fixture_sentences()[3].normalized_text, VOICE, 2.0)
    out = scale_timestamps(ts.timestamps, ratio)
    for orig, new in zip(ts.timestamps, out, strict=True):
        assert abs(new.start_ms - orig.start_ms / ratio) <= 1
        assert abs(new.end_ms - orig.end_ms / ratio) <= 1


# --- stretch_pcm --------------------------------------------------------------------------


@pytest.mark.parametrize("ratio", [1.05, 1.25, 1.5])
def test_syn3_stretch_pcm_length_is_len_over_ratio(ratio: float) -> None:
    from hearnarro.synthesis.stretch import stretch_pcm

    pcm = tone(2.0)
    out = stretch_pcm(pcm, SR, ratio)
    assert len(out) % 2 == 0
    expected = len(pcm) / ratio
    assert abs(len(out) - expected) <= 0.02 * expected  # within 2 %


@pytest.mark.parametrize("ratio", [0.9, 1.0, 1.6, 3.0])
def test_syn3_stretch_pcm_rejects_ratio_outside_1_to_1_5(ratio: float) -> None:
    from hearnarro.synthesis.stretch import stretch_pcm

    with pytest.raises(ValueError):
        stretch_pcm(tone(0.5), SR, ratio)


# --- service: native vs stretched path ----------------------------------------------------


def native_duration_ms(text: str, speed: float) -> int:
    return FakeBackend().synthesize(text, VOICE, speed).duration_ms


@pytest.mark.parametrize("speed", [0.5, 1.0, 1.25, 1.5, 1.75, 2.0])
async def test_syn3_native_path_passes_speed_to_backend(speed: float) -> None:
    seg = fifty_fixture_sentences()[0]
    service, spy, _ = make_service()
    try:
        entry = await service.get_audio(seg.id, VOICE, speed)
    finally:
        await service.shutdown()
    assert [c[2] for c in spy.calls] == [speed]
    assert spy.calls[0][0] == seg.normalized_text
    assert entry.speed == speed
    assert entry.duration_ms == native_duration_ms(seg.normalized_text, speed)


@pytest.mark.parametrize("speed", [2.1, 2.25, 2.5, 2.75, 3.0])
async def test_syn3_stretched_path_synthesizes_at_native_max_then_stretches(speed: float) -> None:
    seg = fifty_fixture_sentences()[0]
    service, spy, cache = make_service()
    try:
        entry = await service.get_audio(seg.id, VOICE, speed)
    finally:
        await service.shutdown()
    assert [c[2] for c in spy.calls] == [2.0]  # native max, never the requested speed
    ratio = speed / 2.0
    at_max = FakeBackend().synthesize(seg.normalized_text, VOICE, 2.0)
    expected_ms = at_max.duration_ms / ratio
    assert abs(entry.duration_ms - expected_ms) <= 0.02 * expected_ms + 1
    assert entry.speed == speed  # cached under the requested speed
    assert cache.ready_ids() == {seg.id}
    for orig, new in zip(at_max.timestamps, entry.timestamps, strict=True):
        assert abs(new.start_ms - orig.start_ms / ratio) <= 1
    # the encoded bytes are the stretched PCM
    wav = next(iter(cache.audio.values()))
    assert len(wav) < len(WavEncoder().encode(at_max.audio, SR))


def test_syn3_stretch_ratio_for_2_25_is_exactly_1_125() -> None:
    assert 2.25 / 2.0 == 1.125


# --- API validation: 0.5 <= speed <= 3.0, speed * 20 integral -----------------------------

VALID = [0.5, 0.55, 0.7, 1.0, 1.25, 1.3, 1.75, 2.0, 2.1, 2.25, 2.7, 2.95, 3.0]
INVALID = ["0.45", "3.05", "0.4", "3.1", "1.23", "1.255", "1.1001", "0", "-1", "10", "abc"]


async def test_syn3_api_speed_validation_0_5_to_3_0_in_0_05_steps(tmp_path: Path) -> None:
    from tests.test_api_audio import ready_document

    async with ready_document(tmp_path) as (client, segments):
        sid = segments[0]["id"]
        for speed in VALID:
            resp = await client.get(f"/audio/{sid}", params={"voice": VOICE, "speed": speed})
            assert resp.status_code == 200, (speed, resp.text)
        for bad in INVALID:
            resp = await client.get(f"/audio/{sid}", params={"voice": VOICE, "speed": bad})
            assert resp.status_code == 422, (bad, resp.text)
