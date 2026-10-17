"""FakeBackend unit tests (SYN-1 timestamps, SYN-2 voices, SYN-4 interface)."""

from __future__ import annotations

import itertools

import pytest

from hearnarro.synthesis.backend import SynthResult, TTSBackend
from hearnarro.synthesis.fake import SAMPLE_RATE, FakeBackend

TEXT = "Zero  trust is a\tsecurity model, not a product."


def test_syn4_fake_backend_satisfies_protocol() -> None:
    backend: TTSBackend = FakeBackend()
    assert backend.name == "fake"
    assert backend.speed_range() == (0.5, 2.0)


def test_syn2_fake_backend_six_voices_both_genders_en_us() -> None:
    voices = FakeBackend().voices()
    assert len(voices) == 6
    assert len({v.id for v in voices}) == 6
    assert {v.gender for v in voices} == {"female", "male"}
    assert sum(v.gender == "female" for v in voices) == 3
    assert all(v.language == "en-US" and v.backend == "fake" for v in voices)
    assert {v.id for v in voices} == {f"fake_{g}{i}" for g in "fm" for i in (1, 2, 3)}


@pytest.mark.parametrize("speed", [0.5, 1.0, 1.3, 2.0])
def test_syn1_fake_backend_80ms_per_word_over_speed(speed: float) -> None:
    result = FakeBackend().synthesize(TEXT, "fake_f1", speed)
    n_words = len(TEXT.split())
    assert result.sample_rate == SAMPLE_RATE == 24_000
    assert len(result.audio) % 2 == 0
    expected_ms = n_words * 80 / speed
    assert abs(result.duration_ms - expected_ms) <= n_words  # rounding per word only
    assert len(result.timestamps) == n_words
    assert set(result.audio) == {0}  # silence


def test_syn1_fake_backend_timestamps_even_and_char_spans_exact() -> None:
    result = FakeBackend().synthesize(TEXT, "fake_m2", 1.0)
    ts = result.timestamps
    assert [t.word for t in ts] == TEXT.split()
    for t in ts:
        assert TEXT[t.char_start : t.char_end] == t.word
    durations = {t.end_ms - t.start_ms for t in ts}
    assert durations == {80}
    assert ts[0].start_ms == 0
    for a, b in itertools.pairwise(ts):
        assert a.end_ms == b.start_ms  # back to back
    assert ts[-1].end_ms == result.duration_ms


def test_syn1_fake_backend_deterministic() -> None:
    a = FakeBackend().synthesize(TEXT, "fake_f3", 1.5)
    b = FakeBackend().synthesize(TEXT, "fake_f3", 1.5)
    assert a == b


def test_syn4_fake_backend_unknown_voice_value_error() -> None:
    with pytest.raises(ValueError):
        FakeBackend().synthesize(TEXT, "af_heart", 1.0)


def test_syn3_fake_backend_rejects_speed_outside_native_range() -> None:
    with pytest.raises(ValueError):
        FakeBackend().synthesize(TEXT, "fake_f1", 2.5)


@pytest.mark.parametrize("text", ["", "   \n\t "])
def test_syn1_fake_backend_empty_text_empty_result(text: str) -> None:
    result = FakeBackend().synthesize(text, "fake_f1", 1.0)
    assert result == SynthResult(audio=b"", sample_rate=SAMPLE_RATE, timestamps=[])
    assert result.duration_ms == 0
