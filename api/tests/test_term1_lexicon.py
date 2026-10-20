"""TERM-1 shipped academic lexicon and TERM-2 per-document respellings in the Kokoro backend.

Precedence: a user respelling (``SynthContext.lexicon``) > ``lexicon_overrides.OVERRIDES`` >
``lexicon_academic.ACADEMIC`` > misaki's gold lexicon > misaki's general lexicon.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import cache
from typing import Any

import pytest

from hearnarro.synthesis import lexicon_academic as la
from hearnarro.synthesis import lexicon_overrides as lo
from hearnarro.synthesis.backend import SynthContext

DOMAINS = {"math", "stats", "physics", "chem", "bio", "cs", "latin_greek", "surname"}


@dataclass
class Tok:
    text: str
    phonemes: str | None


@cache
def _vocab() -> set[str]:
    from hearnarro.synthesis.kokoro_backend import model_vocab

    return model_vocab()


def _g2p() -> Any:
    """The backend's G2P front-end without model weights (as EVAL-4 builds it), or skip."""
    try:
        from hearnarro.synthesis import kokoro_backend

        logging.getLogger(kokoro_backend.__name__).setLevel(logging.ERROR)
        return kokoro_backend.build_g2p(False, _vocab())
    except Exception as e:  # noqa: BLE001 - no misaki/spaCy/config here: skip
        pytest.skip(f"voice front-end unavailable: {type(e).__name__}: {e}")


def _first(g2p: Any, text: str) -> str:
    _, tokens = g2p(text)
    return tokens[0].phonemes


# claim 1: shape, keys, symbols in the model vocab


def test_term1_academic_keyed_by_eight_domains_and_flat_merges() -> None:
    assert set(la.ACADEMIC) == DOMAINS
    flat = la.flat()
    assert sum(len(v) for v in la.ACADEMIC.values()) >= len(flat) > 0
    for entries in la.ACADEMIC.values():
        for word, ps in entries.items():
            assert word == word.lower() and ps and " " not in ps
            assert word in flat


@pytest.mark.model
def test_term1_academic_phonemes_in_model_vocab() -> None:
    vocab = _vocab()
    missing = {w: [c for c in ps if c not in vocab] for w, ps in la.flat().items()}
    assert {w: m for w, m in missing.items() if m} == {}


# claim 2: OVERRIDES > ACADEMIC > misaki


def test_term1_precedence_overrides_over_academic_over_misaki(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    misaki_says = _first(_g2p(), "Fourier")  # ACADEMIC applied: fˈʊɹiˌA
    assert misaki_says == la.ACADEMIC["math"]["fourier"]
    monkeypatch.setitem(lo.OVERRIDES, "fourier", "fˈʊɹiəɹ")  # same word in both tables
    g2p = _g2p()
    for form in ("Fourier", "fourier"):
        assert _first(g2p, form) == "fˈʊɹiəɹ"  # OVERRIDES wins
    assert _first(g2p, "Cauchy") == la.ACADEMIC["math"]["cauchy"]  # ACADEMIC over misaki
    assert _first(g2p, "kernel") == "kˈɜɹnᵊl"  # neither table: misaki's own lexicon


@pytest.mark.parametrize("word", ["Zhang", "Xu", "Nguyen", "Erdős", "Poisson", "Feynman"])
def test_term1_capitalised_short_names_use_the_entry(word: str) -> None:
    # misaki does not lower-case a short proper noun before the gold lookup
    assert _first(_g2p(), f"{word} wrote it.") == la.flat()[word.lower()]


# claim 4: a respelling in SynthContext.lexicon reaches the phonemes


def test_term2_lookup_extra_table_wins_with_suffixes() -> None:
    extra = {"uber": "ˈubəɹX", "cauchy": "kˈOʃi"}
    assert lo.lookup("Uber", extra) == ("ˈubəɹX", "uber")  # respelling over OVERRIDES
    assert lo.lookup("Cauchy's", extra) == ("kˈOʃiz", "cauchy")
    assert lo.lookup("Uber") == ("ˈubəɹ", "uber")  # no table: unchanged
    tokens = [Tok("the", "ðə"), Tok("Cauchy", "kˈɔʧi")]
    assert lo.apply(tokens, extra) == ["cauchy"]
    assert tokens[1].phonemes == "kˈOʃi"


def test_term2_respellings_converted_through_the_backend_g2p() -> None:
    from hearnarro.synthesis.kokoro_backend import respelling_phonemes

    g2p = _g2p()
    table = respelling_phonemes(g2p, {"Kernel": "Koh-shee", "tuple": "too pull"})
    assert set(table) == {"kernel", "tuple"}
    assert table["kernel"] == _first(g2p, "Koh") + _first(g2p, "shee")
    assert table["kernel"] != _first(g2p, "kernel")
    assert table["tuple"] == _first(g2p, "too") + " " + _first(g2p, "pull")


def test_term2_fake_backend_ignores_lexicon() -> None:
    from hearnarro.synthesis.fake import FakeBackend

    fake = FakeBackend()
    voice = fake.voices()[0].id
    ctx = SynthContext(lexicon={"cauchy": "Koh-shee"})
    text = "The Cauchy sequence."
    assert fake.synthesize(text, voice, 1.0, ctx) == fake.synthesize(text, voice, 1.0)


@pytest.mark.model
def test_term2_kokoro_respelling_reaches_model_phonemes() -> None:
    from hearnarro.synthesis.kokoro_backend import PINNED_REVISION, KokoroBackend

    b = KokoroBackend(revision=PINNED_REVISION)
    text = "The kernel and Uber's kernels."
    plain = {t.text: t.phonemes for t in b._tokens(text, False)}
    ctx = SynthContext(lexicon={"kernel": "Koh-shee", "uber": "oo-bah"}, document_id=7)
    tokens = b._tokens(text, False, ctx)
    got = {t.text: t.phonemes for t in tokens}
    respelled = b._respellings(ctx, False)
    assert got["kernel"] == respelled["kernel"] != plain["kernel"]
    assert got["kernels"] == lo._plural(respelled["kernel"])
    assert got["Uber's"] == lo._plural(respelled["uber"])  # respelling over OVERRIDES
    assert b._respellings(ctx, False) is respelled  # converted once per context
    result = b.synthesize(text, "af_heart", 1.0, ctx)
    words = [w.word.rstrip(".") for w in result.timestamps]
    assert words == ["The", "kernel", "and", "Uber's", "kernels"]
