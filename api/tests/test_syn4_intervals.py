"""SYN-4 / ING-6: square brackets glued to a digit ("[0, 1)", "[0, 2]") are read aloud. spaCy tags
such a "[" as XX instead of -LRB-, so misaki's ``retokenize`` does not treat it as punctuation and
merges it with the digit into one word "[0" that has no pronunciation (silence). The backend reads
square brackets as round ones before G2P. Needs ``HEARNARRO_TEST_MODEL=1``."""

from __future__ import annotations

import functools

import pytest


@functools.cache
def _backend():
    from hearnarro.synthesis.kokoro_backend import PINNED_REVISION, KokoroBackend

    return KokoroBackend(revision=PINNED_REVISION)


def _tokens(text: str) -> list:
    return _backend()._tokens(text, british=False)


def _phon(word: str) -> str:
    return {t.text: t.phonemes for t in _tokens(word)}[word]


@pytest.mark.model
def test_syn4_interval_half_open_digits_spoken() -> None:
    text = "on R3 × [0, 1) satisfying"
    tokens = _tokens(text)
    ps = "".join(t.phonemes + t.whitespace for t in tokens)
    assert _phon("0") in ps and _phon("1") in ps
    assert [t.text for t in tokens if t.text in ("[", "0")] == ["[", "0"]


@pytest.mark.model
def test_syn4_interval_closed_digits_spoken() -> None:
    tokens = _tokens("in K × [0, 2], and")
    by_text = {t.text: t.phonemes for t in tokens}
    assert by_text["0"] == _phon("0") and by_text["2"] == _phon("2")
    assert "[" in by_text and "]" in by_text
