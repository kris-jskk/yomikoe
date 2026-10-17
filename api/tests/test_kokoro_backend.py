"""KokoroBackend (SYN-2 voices, SYN-3 native speed, SYN-4 backend; D15). Model tests need
``HEARNARRO_TEST_MODEL=1``; the pure helpers below always run."""

from __future__ import annotations

import functools
import logging
import re

import pytest

from hearnarro.synthesis.kokoro_backend import (
    PINNED_REVISION,
    _Timed,
    arpabet_to_kokoro,
    word_timestamps,
)

SENTENCE = "The quick brown fox jumps over the lazy dog, and 3.2 percent of readers noticed."
OOV_SENTENCE = "Kubernetes orchestrates pods across HearNarro's Zygalski nodes."


def test_syn4_kokoro_revision_is_pinned_hash() -> None:
    from hearnarro.settings import DEFAULT_KOKORO_REVISION

    assert re.fullmatch(r"[0-9a-f]{40}", PINNED_REVISION)
    assert DEFAULT_KOKORO_REVISION == PINNED_REVISION


def test_syn4_arpabet_to_kokoro_stress_and_vowels() -> None:
    assert arpabet_to_kokoro(["Z", "IH0", "G", "AA1", "L", "S", "K", "IY0"]) == "zɪɡˈɑlski"
    assert arpabet_to_kokoro(["K", "AH0", "B", "ER1"]) == "kəbˈɜɹ"
    assert arpabet_to_kokoro(["G", "OW1"], british=True) == "ɡˈQ"


def test_syn1_word_timestamps_every_word_gets_a_span() -> None:
    text = "Hello, odd § world"
    timed = [
        _Timed("Hello", 100, 400),
        _Timed(",", None, None),
        _Timed("odd", 500, 700),
        _Timed("§", None, None),  # empty phonemes: zero-length at previous end
        _Timed("world", 800, 5000),  # clamped to duration
    ]
    ts = word_timestamps(text, timed, duration_ms=1200)
    assert [(t.word, t.start_ms, t.end_ms) for t in ts] == [
        ("Hello,", 100, 400),
        ("odd", 500, 700),
        ("§", 700, 700),
        ("world", 800, 1200),
    ]
    assert all(text[t.char_start : t.char_end] == t.word for t in ts)


@functools.cache
def _backend():
    from hearnarro.synthesis.kokoro_backend import KokoroBackend

    return KokoroBackend(revision=PINNED_REVISION)


def _check_invariants(text: str, result) -> None:
    ts = result.timestamps
    assert ts
    assert [t.word for t in ts] == text.split()
    prev = 0
    for t in ts:
        assert prev <= t.start_ms <= t.end_ms <= result.duration_ms
        assert 0 <= t.char_start < t.char_end <= len(text)
        assert text[t.char_start : t.char_end] == t.word
        prev = t.end_ms


@pytest.mark.model
def test_syn2_kokoro_voices_both_genders_en() -> None:
    voices = _backend().voices()
    assert len(voices) >= 6
    assert {v.gender for v in voices} == {"female", "male"}
    assert {v.language for v in voices} <= {"en-US", "en-GB"}
    assert all(v.backend == "kokoro" and v.gender[0] == v.id[1] for v in voices)
    assert _backend().speed_range() == (0.5, 2.0)


@pytest.mark.model
@pytest.mark.parametrize("voice", ["af_heart", "bm_george"])
def test_syn1_kokoro_sentence_timestamps_valid(voice: str) -> None:
    result = _backend().synthesize(SENTENCE, voice, 1.0)
    assert result.sample_rate == 24_000
    assert result.duration_ms > 300
    _check_invariants(SENTENCE, result)
    assert all(t.end_ms > t.start_ms for t in result.timestamps)


@pytest.mark.model
def test_syn4_kokoro_oov_words_are_spoken_and_timed(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING, logger="hearnarro.synthesis.kokoro_backend"):
        result = _backend().synthesize(OOV_SENTENCE, "af_heart", 1.0)
    _check_invariants(OOV_SENTENCE, result)
    assert all(t.end_ms > t.start_ms for t in result.timestamps)  # nothing dropped silently
    warned = " ".join(r.getMessage() for r in caplog.records)
    assert "Kubernetes" in warned and "Zygalski" in warned


@pytest.mark.model
def test_syn3_kokoro_native_speed_range_scales_duration() -> None:
    slow = _backend().synthesize(SENTENCE, "af_heart", 0.5).duration_ms
    fast = _backend().synthesize(SENTENCE, "af_heart", 2.0).duration_ms
    assert 2.8 <= slow / fast <= 4.2  # spike 275: 11.55 s / 3.33 s = 3.47
    with pytest.raises(ValueError):
        _backend().synthesize(SENTENCE, "af_heart", 2.5)
