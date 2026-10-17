"""SYN-4: custom pronunciations win over misaki's fallback, with possessive/plural suffixes."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from hearnarro.synthesis import lexicon_overrides as lo


@dataclass
class Tok:
    text: str
    phonemes: str | None


@pytest.mark.parametrize(
    ("token", "expected"),
    [
        ("Uber", "ˈubəɹ"),
        ("UBER", "ˈubəɹ"),
        ("uber", "ˈubəɹ"),
        ("Uber's", "ˈubəɹz"),
        ("Uber’s", "ˈubəɹz"),
        ("Ubers", "ˈubəɹz"),
    ],
)
def test_syn4_override_lookup_case_and_suffixes(token: str, expected: str) -> None:
    hit = lo.lookup(token)
    assert hit is not None and hit[0] == expected


@pytest.mark.parametrize("token", ["Ubered", "Tuber", "U", "the"])
def test_syn4_override_lookup_misses(token: str) -> None:
    assert lo.lookup(token) is None


def test_syn4_override_plural_after_voiceless_and_sibilant() -> None:
    assert lo._plural("kˈæt") == "kˈæts"
    assert lo._plural("bˈʌs") == "bˈʌsɪz"


def test_syn4_override_wins_over_fallback_phonemes() -> None:
    tokens = [Tok("an", "ɐn"), Tok("Uber", "jˈubəɹ"), Tok("ride", "ɹˈId")]  # fallback guess
    assert lo.apply(tokens) == ["uber"]
    assert [t.phonemes for t in tokens] == ["ɐn", "ˈubəɹ", "ɹˈId"]


def test_syn4_override_keys_lower_case() -> None:
    assert all(k == k.lower() and v for k, v in lo.OVERRIDES.items())
