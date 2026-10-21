"""SYN-1: per-clip silence trim to a fixed pad (trim.py), timestamps shifted; service wiring."""

from __future__ import annotations

import dataclasses
import itertools

import numpy as np
import pytest

from tests.conftest import fifty_fixture_sentences, make_service
from yomikoe.settings import SettingsError, load_settings
from yomikoe.synthesis.backend import SynthResult, WordTimestamp
from yomikoe.synthesis.fake import FakeBackend
from yomikoe.synthesis.trim import trim_silence

SR = 24_000
TH = 10 ** (-40 / 20)


def _pcm(*parts: tuple[str, int]) -> bytes:
    """('s', ms) silence or ('t', ms) a -12 dBFS 220 Hz tone, concatenated, PCM16."""
    chunks = []
    for kind, ms in parts:
        n = SR * ms // 1000
        if kind == "s":
            chunks.append(np.zeros(n))
        else:
            t = np.arange(n) / SR
            chunks.append(0.25 * np.sin(2 * np.pi * 220 * t) + 0.01)  # offset: never 0
    return (np.concatenate(chunks) * 32767).astype("<i2").tobytes()


def _silence_ms(pcm: bytes) -> tuple[float, float]:
    x = np.frombuffer(pcm, dtype="<i2").astype(np.float64) / 32768.0
    loud = np.flatnonzero(np.abs(x) > TH)
    return loud[0] * 1000 / SR, (len(x) - 1 - loud[-1]) * 1000 / SR


def _ts(*spans: tuple[int, int]) -> list[WordTimestamp]:
    return [WordTimestamp(f"w{i}", a, b, i * 3, i * 3 + 2) for i, (a, b) in enumerate(spans)]


def _dur(pcm: bytes) -> int:
    return int(len(pcm) // 2 * 1000 / SR)


def _invariants(ts: list[WordTimestamp], duration_ms: int) -> None:
    for t in ts:
        assert 0 <= t.start_ms <= t.end_ms <= duration_ms, t
    for a, b in itertools.pairwise(ts):
        assert a.start_ms <= b.start_ms and a.end_ms <= b.start_ms


def test_syn1_trim_cuts_lead_and_tail_to_pads_and_shifts_timestamps() -> None:
    pcm = _pcm(("s", 500), ("t", 1000), ("s", 600))
    ts = _ts((520, 900), (900, 1480))
    out, new = trim_silence(pcm, SR, ts)
    lead, tail = _silence_ms(out)
    assert abs(lead - 60) <= 1 and abs(tail - 150) <= 1
    assert [(t.start_ms, t.end_ms) for t in new] == [(80, 460), (460, 1040)]  # -440 ms
    assert [(t.char_start, t.char_end, t.word) for t in new] == [
        (t.char_start, t.char_end, t.word) for t in ts
    ]
    _invariants(new, _dur(out))


def test_syn1_trim_pads_are_parameters() -> None:
    out, _ = trim_silence(_pcm(("s", 500), ("t", 400), ("s", 600)), SR, [], lead_ms=0, tail_ms=0)
    lead, tail = _silence_ms(out)
    assert lead <= 1 and tail <= 1


def test_syn1_trim_no_silence_is_unchanged() -> None:
    pcm = _pcm(("t", 800))
    ts = _ts((0, 400), (400, 800))
    assert trim_silence(pcm, SR, ts) == (pcm, ts)


def test_syn1_trim_short_silence_inside_pads_is_unchanged() -> None:
    pcm = _pcm(("s", 40), ("t", 800), ("s", 100))
    ts = _ts((40, 840))
    assert trim_silence(pcm, SR, ts) == (pcm, ts)


def test_syn1_trim_all_silence_and_empty_are_unchanged() -> None:
    pcm = _pcm(("s", 900))
    ts = _ts((0, 450), (450, 900))
    assert trim_silence(pcm, SR, ts) == (pcm, ts)
    assert trim_silence(b"", SR, []) == (b"", [])


def test_syn1_trim_keeps_20ms_before_the_first_word() -> None:
    """The model may time the first word before its audible onset: the head cut stops 20 ms
    before the first word's start_ms."""
    pcm = _pcm(("s", 500), ("t", 600), ("s", 100))
    ts = _ts((200, 700), (700, 1100))
    out, new = trim_silence(pcm, SR, ts)
    assert new[0].start_ms == 20
    assert _dur(pcm) - _dur(out) == 180
    _invariants(new, _dur(out))


def test_syn1_trim_never_cuts_audio_above_threshold() -> None:
    quiet = int(32767 * 10 ** (-38 / 20))  # -38 dBFS: above the -40 threshold
    x = np.zeros(SR)  # 1 s
    x[SR // 10] = quiet  # a lone sample at 100 ms
    x[7 * SR // 10] = -quiet  # and at 700 ms
    pcm = x.astype("<i2").tobytes()
    out, _ = trim_silence(pcm, SR, [])
    y = np.frombuffer(out, dtype="<i2")
    assert int(np.abs(y).max()) == quiet and int((np.abs(y) == quiet).sum()) == 2
    lead, tail = _silence_ms(out)
    assert abs(lead - 60) <= 1 and abs(tail - 150) <= 1


def test_syn1_trim_clamps_end_ms_to_the_new_duration() -> None:
    """Kokoro times the last word past its audible end (results 369): after the tail cut its
    end_ms is clamped to the new duration."""
    pcm = _pcm(("s", 300), ("t", 700), ("s", 600))
    ts = _ts((300, 700), (700, 1500))
    out, new = trim_silence(pcm, SR, ts)
    assert new[-1].end_ms == _dur(out)
    _invariants(new, _dur(out))


class _PaddedBackend(FakeBackend):
    """FakeBackend with tone instead of zeros and 300 ms / 400 ms of silence around it."""

    def synthesize(self, text: str, voice_id: str, speed: float) -> SynthResult:
        r = super().synthesize(text, voice_id, speed)
        body = _pcm(("t", r.duration_ms))
        audio = _pcm(("s", 300)) + body + _pcm(("s", 400))
        ts = [
            dataclasses.replace(t, start_ms=t.start_ms + 300, end_ms=t.end_ms + 300)
            for t in r.timestamps
        ]
        return SynthResult(audio=audio, sample_rate=r.sample_rate, timestamps=ts)


@pytest.mark.parametrize("speed", [1.0, 2.0, 2.5])
async def test_syn1_service_trims_each_clip_before_stretch(speed: float) -> None:
    service, _, _ = make_service(_PaddedBackend())
    try:
        seg = fifty_fixture_sentences()[0]
        entry = await service.get_audio(seg.id, "fake_f1", speed)
        raw = FakeBackend().synthesize(seg.normalized_text, "fake_f1", min(speed, 2.0))
        ratio = speed / 2.0 if speed > 2.0 else 1.0
        expected = (raw.duration_ms + 60 + 150) / ratio
        assert abs(entry.duration_ms - expected) <= 3, (entry.duration_ms, expected)
        assert abs(entry.timestamps[0].start_ms - 60 / ratio) <= 2
        _invariants(entry.timestamps, entry.duration_ms)
    finally:
        await service.shutdown()


async def test_syn1_service_trim_pads_from_constructor() -> None:
    service, _, _ = make_service(_PaddedBackend())
    service.trim_lead_ms, service.trim_tail_ms = 0, 0
    try:
        seg = fifty_fixture_sentences()[0]
        entry = await service.get_audio(seg.id, "fake_f1", 1.0)
        raw = FakeBackend().synthesize(seg.normalized_text, "fake_f1", 1.0)
        assert abs(entry.duration_ms - (raw.duration_ms + 20)) <= 2  # 20 ms first-word guard
    finally:
        await service.shutdown()


def test_syn1_trim_settings_defaults_and_env() -> None:
    s = load_settings({}, kokoro_installed=False)
    assert (s.trim_lead_ms, s.trim_tail_ms) == (60, 150)
    env = {"YOMIKOE_TRIM_LEAD_MS": "30", "YOMIKOE_TRIM_TAIL_MS": "250"}
    s = load_settings(env, kokoro_installed=False)
    assert (s.trim_lead_ms, s.trim_tail_ms) == (30, 250)
    with pytest.raises(SettingsError):
        load_settings({"YOMIKOE_TRIM_TAIL_MS": "-1"}, kokoro_installed=False)
    with pytest.raises(SettingsError):
        load_settings({"YOMIKOE_TRIM_LEAD_MS": "x"}, kokoro_installed=False)
