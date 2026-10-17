"""SYN-4: a mixed-case token ending in a run of 2+ capitals ("OpenAI", "GenAI", "xAI") is read as
its word part followed by the acronym decision for the capital run ("open A I"). The split is a
pure function; the backend tests need ``HEARNARRO_TEST_MODEL=1``."""

from __future__ import annotations

import functools

import pytest


@pytest.mark.parametrize(
    ("token", "split"),
    [
        ("OpenAI", ("Open", "AI", "")),
        ("OpenAI's", ("Open", "AI", "'s")),
        ("GenAI", ("Gen", "AI", "")),
        ("xAI", ("x", "AI", "")),
        ("iPhone", None),
        ("YouTube", None),
        ("NASA", None),
        ("PDFs", None),
        ("AI", None),
        ("open", None),
    ],
)
def test_syn4_split_camel_acronym(token: str, split: tuple[str, str, str] | None) -> None:
    from hearnarro.synthesis.acronyms import split_camel_acronym

    assert split_camel_acronym(token) == split


@functools.cache
def _backend():
    from hearnarro.synthesis.kokoro_backend import PINNED_REVISION, KokoroBackend

    return KokoroBackend(revision=PINNED_REVISION)


def _tokens(text: str) -> list:
    return _backend()._tokens(text, british=False)


@pytest.mark.model
def test_syn4_camel_acronym_openai_is_open_then_spelled_a_i() -> None:
    tokens = _tokens("OpenAI released a model.")
    texts = [t.text for t in tokens]
    assert texts[:3] == ["Open", "A", "I"]
    assert [t.whitespace for t in tokens[:3]] == ["", "", " "]
    look = _backend()._g2p_for(british=False).fallback._look
    assert tokens[0].phonemes == look("open").replace("ˈ", "ˌ")
    assert "".join(t.phonemes for t in tokens[:3]) == "ˌOpᵊnˌAˈI"


@pytest.mark.model
def test_syn4_camel_acronym_possessive_stays_on_spelled_tail() -> None:
    tokens = _tokens("OpenAI's model.")
    assert [t.text for t in tokens[:3]] == ["Open", "A", "I's"]
    assert tokens[2].phonemes == "ˈIz"
    assert "".join(t.phonemes for t in tokens[:3]) == "ˌOpᵊnˌAˈIz"


@pytest.mark.model
def test_syn4_camel_acronym_ordinary_camel_case_unchanged() -> None:
    text = "My iPhone plays YouTube videos."
    tokens = _tokens(text)
    texts = [t.text for t in tokens]
    assert "iPhone" in texts and "YouTube" in texts
    assert not {"i", "Phone", "You", "Tube"} & set(texts)
    plain = {t.text: t.phonemes for t in _backend()._g2p_for(british=False)(text)[1]}
    by_text = {t.text: t.phonemes for t in tokens}
    assert by_text["iPhone"] == plain["iPhone"] and by_text["YouTube"] == plain["YouTube"]


@pytest.mark.model
def test_syn4_camel_acronym_macos_spells_os() -> None:
    tokens = _tokens("macOS")
    assert [t.text for t in tokens] == ["mac", "O", "S"]


@pytest.mark.model
def test_syn1_camel_acronym_one_timestamp_per_word() -> None:
    text = "OpenAI's GenAI and xAI."
    result = _backend().synthesize(text, "af_heart", 1.0)
    assert [t.word for t in result.timestamps] == text.split()
    assert all(text[t.char_start : t.char_end] == t.word for t in result.timestamps)
    assert all(t.end_ms > t.start_ms for t in result.timestamps)


@pytest.mark.parametrize(
    ("token", "split"),
    [("OPENAI", ("OPEN", "AI")), ("FORMAT", None), ("NVIDIA", None), ("ERIC'S", None)],
)
def test_syn4_split_caps_compound(token: str, split: tuple[str, str] | None) -> None:
    from hearnarro.synthesis.acronyms import split_caps_compound

    known = {"open", "format", "eric"}.__contains__
    assert split_caps_compound(token, lambda w: known(w.lower())) == split


@pytest.mark.model
def test_syn4_caps_compound_openai_is_open_then_spelled_a_i() -> None:
    tokens = _tokens("OPENAI")
    assert [t.text for t in tokens] == ["OPEN", "A", "I"]
    assert "".join(t.phonemes for t in tokens) == "ˌOpᵊnˌAˈI"


@pytest.mark.model
@pytest.mark.parametrize("word", ["FORMAT", "NVIDIA", "NAVIER"])
def test_syn4_caps_compound_known_or_unsplittable_word_unchanged(word: str) -> None:
    tokens = _tokens(word)
    assert [t.text for t in tokens] == [word]
    plain = _backend()._g2p_for(british=False)(word.capitalize())[1]
    assert tokens[0].phonemes == plain[0].phonemes


@pytest.mark.model
def test_syn4_caps_compound_outside_caps_context() -> None:
    tokens = _tokens("n≥J OPENAI")
    assert [t.text for t in tokens][-3:] == ["OPEN", "A", "I"]
    assert "".join(t.phonemes for t in tokens[-3:]) == "ˌOpᵊnˌAˈI"
