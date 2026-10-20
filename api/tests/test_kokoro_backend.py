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


ONSET_SENTENCES = [
    "On the other hand, we’re also taught from a young age to finish your books.",
    "Weight pruning removes parameters from a trained network to reduce its size.",
    "That split is what lets the reader start playback before the rest is ready.",
]


def _first_word_onset(result) -> tuple[float, float, int]:
    """(onset ms: first sample above -35 dBFS, RMS over the first word's timestamp window,
    the first word's start ms). The window, not a fixed 100 ms: at 2.0 a short word's first
    100 ms already includes the next word's stop closure."""
    import numpy as np

    x = np.frombuffer(result.audio, dtype="<i2").astype(np.float64) / 32768.0
    loud = np.flatnonzero(np.abs(x) > 10 ** (-35 / 20))
    onset = loud[0] * 1000 / result.sample_rate if len(loud) else float("inf")
    start = result.timestamps[0].start_ms
    end = result.timestamps[0].end_ms
    window = x[start * result.sample_rate // 1000 : end * result.sample_rate // 1000]
    return onset, float(np.sqrt(np.mean(window**2))), start


@pytest.mark.model
@pytest.mark.parametrize("text", ONSET_SENTENCES)
def test_syn3_kokoro_first_word_not_clipped_at_fast_native_speeds(text: str) -> None:
    """At 2.0 the model's ~250 ms dead start swallowed the first word once BOS shrank with
    speed (results 343). The first word must be audible at its timestamp at every speed."""
    import torch

    torch.manual_seed(0)  # the decoder draws noise; fix it so the margins are reproducible
    _, ref_rms, _ = _first_word_onset(_backend().synthesize(text, "af_heart", 1.0))
    for speed in (1.0, 1.5, 2.0):
        torch.manual_seed(0)
        result = _backend().synthesize(text, "af_heart", speed)
        _check_invariants(text, result)
        onset, rms, start = _first_word_onset(result)
        assert onset <= start + 60, f"speed {speed}: onset {onset:.0f} ms, first word {start} ms"
        assert rms >= 0.5 * ref_rms, f"speed {speed}: first-word RMS {rms:.4f} vs {ref_rms:.4f}"


ACRONYM_SENTENCE = "The CEO watched a TED talk about NASA and PDF files."


@pytest.mark.model
def test_syn4_kokoro_acronyms_spoken_or_spelled_one_timestamp_per_word() -> None:
    b = _backend()
    tokens = b._tokens(ACRONYM_SENTENCE, british=False)
    texts = [t.text for t in tokens]
    assert "TED" in texts and "NASA" in texts  # single word tokens
    assert "CEO" not in texts and "PDF" not in texts  # replaced by letter tokens
    lex = b._g2p_for(british=False).lexicon
    by_text = {t.text: t.phonemes for t in tokens}
    assert by_text["TED"] == lex.golds["ted"]
    assert by_text["NASA"] == lex.golds["NASA"]
    c = texts.index("C")
    assert texts[c : c + 3] == ["C", "E", "O"]
    assert [t.whitespace for t in tokens[c : c + 3]] == ["", "", " "]
    assert "".join(t.phonemes for t in tokens[c : c + 3]) == lex.get_NNP("CEO")[0]
    p = texts.index("P")
    assert texts[p : p + 3] == ["P", "D", "F"]
    result = b.synthesize(ACRONYM_SENTENCE, "af_heart", 1.0)
    _check_invariants(ACRONYM_SENTENCE, result)
    spans = {t.word: (t.char_start, t.char_end, t.end_ms - t.start_ms) for t in result.timestamps}
    for word in ("CEO", "TED", "NASA", "PDF"):
        start = ACRONYM_SENTENCE.index(word)
        assert spans[word][:2] == (start, start + len(word))
        assert spans[word][2] > 0
    assert spans["CEO"][2] > spans["TED"][2]  # three letters take longer than one syllable


@pytest.mark.model
def test_syn4_kokoro_document_definition_spells_ted() -> None:
    from hearnarro.synthesis.backend import SynthContext

    text = "The Transferable Erosion Deposit (TED) rose, and TED values fell."
    ctx = SynthContext(acronyms={"TED": "Transferable Erosion Deposit"}, document_id=1)
    texts = [t.text for t in _backend()._tokens(text, british=False, context=ctx)]
    assert "TED" not in texts and texts.count("T") == 2
    plain = [t.text for t in _backend()._tokens(text, british=False)]
    assert plain.count("TED") == 2
    _check_invariants(text, _backend().synthesize(text, "af_heart", 1.0, context=ctx))


@pytest.mark.model
def test_syn4_kokoro_json_respelled_as_jason() -> None:
    b = _backend()
    tokens = b._tokens("Parse the JSON file.", british=False)
    json_ps = next(t.phonemes for t in tokens if t.text == "JSON")
    assert json_ps == b._g2p_for(british=False).fallback._look("Jason")


UBER_SENTENCE = "I took an Uber to the TED talk."


@pytest.mark.model
def test_syn4_kokoro_lexicon_override_uber(caplog: pytest.LogCaptureFixture) -> None:
    from hearnarro.synthesis.backend import SynthContext
    from hearnarro.synthesis.lexicon_academic import flat
    from hearnarro.synthesis.lexicon_overrides import OVERRIDES

    b = _backend()
    assert all(c in b._vocab for ps in OVERRIDES.values() for c in ps)
    assert all(c in b._vocab for ps in flat().values() for c in ps)  # TERM-1
    ctx = SynthContext(acronyms={"XYZ": "Some Other Thing"}, document_id=4242)
    with caplog.at_level(logging.INFO, logger="hearnarro.synthesis.kokoro_backend"):
        by_text = {t.text: t.phonemes for t in b._tokens(UBER_SENTENCE, False, ctx)}
        b._tokens("Two Ubers and Uber's app.", False, ctx)
    assert by_text["Uber"] == "ˈubəɹ"  # the 'u' vowel, not 'j' (fallback said jˈubəɹ)
    assert by_text["TED"] == "tˈɛd"
    logged = [r.getMessage() for r in caplog.records if "override" in r.getMessage()]
    assert logged == ["pronunciation override document=4242 entry='uber'"]  # once per document
    _check_invariants(UBER_SENTENCE, b.synthesize(UBER_SENTENCE, "af_heart", 1.0))


@pytest.mark.model
def test_syn4_kokoro_caps_heading_read_as_words() -> None:
    """ERIC'S NOTE (the Almanack heading) was spelled "E R I C S" by misaki's get_NNP."""
    from pathlib import Path

    b = _backend()
    tokens = b._tokens("ERIC'S NOTE", british=False)
    assert [t.text for t in tokens] == ["ERIC'S", "NOTE"]  # two word tokens, original text
    lex = b._g2p_for(british=False).lexicon
    eric = tokens[0].phonemes.lstrip("ˈˌ")
    assert eric.startswith("ɛ"), tokens[0].phonemes  # the vowel of "Eric", not "E R I C"
    assert not tokens[0].phonemes.startswith(lex.get_NNP("ERIC")[0])
    part = [t.text for t in b._tokens("PART I: WEALTH", british=False)]
    assert part == ["PART", "I", ":", "WEALTH"]  # never "P A R T"
    mixed = [t.text for t in b._tokens("The CEO read ERIC'S NOTE", british=False)]
    assert mixed == ["The", "C", "E", "O", "read", "ERIC'S", "NOTE"]
    result = b.synthesize("ERIC'S NOTE", "af_heart", 1.0)
    _check_invariants("ERIC'S NOTE", result)
    assert [t.word for t in result.timestamps] == ["ERIC'S", "NOTE"]
    out = Path.home() / "hearnarro-m1" / "audio_samples" / "erics_note_1.0x.wav"
    if out.parent.is_dir():
        import wave

        with wave.open(str(out), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(result.sample_rate)
            w.writeframes(result.audio)


@pytest.mark.model
def test_syn4_kokoro_acronym_possessive_and_plural_spelled() -> None:
    b = _backend()
    text = "The CEO's PDFs."
    tokens = b._tokens(text, british=False)
    texts = [t.text for t in tokens]
    assert texts == ["The", "C", "E", "O's", "P", "D", "Fs", "."]
    by = {t.text: t.phonemes for t in tokens}
    assert by["O's"].endswith("z") and by["Fs"].endswith("s")
    result = b.synthesize(text, "af_heart", 1.0)
    _check_invariants(text, result)
    assert [t.word for t in result.timestamps] == ["The", "CEO's", "PDFs."]
