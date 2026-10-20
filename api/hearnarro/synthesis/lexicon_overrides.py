"""Custom pronunciations, consulted before misaki's lexicon and the OOV fallback (SYN-4).

Format: ``OVERRIDES`` maps a word, lower case, to its phonemes in misaki/Kokoro's US phoneme
alphabet (the strings misaki's ``G2P`` emits: ``ˈ``/``ˌ`` before the stressed vowel; ``A`` = "ay",
``I`` = "eye", ``O`` = "oh", ``W`` = "ow", ``ɹ`` = r, ``ə`` = schwa, ``ʃ`` = sh, ``ʤ`` = j). To add a
pronunciation, add one line here; a backend test checks every symbol is in the model's vocab.

Matching is case-insensitive on the whole token ("Uber", "UBER", "uber"). A possessive ("Uber's",
"Uber’s") or plural ("Ubers") of an entry gets the entry's phonemes plus ``s`` after a voiceless
consonant, ``ɪz`` after a sibilant, else ``z``. This file is the escape hatch, kept minimal: the
lexicon tiers (misaki's gold/silver lexicon, then the CMU Pronouncing Dictionary) cover most
words, and an entry belongs here only when every tier is missing or wrong for it ("Uber": misaki
has none, cmudict and the g2p fallback say "YOO-ber"; ``_agent/results/367_uber_before.txt``,
``368_coverage.md``). Academic terms live in ``lexicon_academic`` (TERM-1), below this table.

``lookup`` and ``apply`` take an optional ``extra`` table in the same format (word -> phonemes),
consulted before ``OVERRIDES``: the Kokoro backend passes a document's user respellings
(``SynthContext.lexicon``, TERM-2) there after converting each through its own G2P.

The Kokoro backend writes these entries into misaki's gold lexicon (so misaki's own suffix and
context rules see them and the fallback is not reached), then sets the phonemes of every token
that ``lookup`` matches, and logs each entry used once per document at INFO.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

OVERRIDES: dict[str, str] = {
    # misaki has no entry; cmudict has Y UW1 B ER0 ("YOO-ber") and the g2p fallback agrees
    "uber": "ˈubəɹ",
}

_VOICELESS = set("ptkfθ")
_SIBILANT = set("szʃʒʧʤ")


def _plural(ps: str) -> str:
    last = ps.rstrip("ˈˌ")[-1:]
    return ps + ("ɪz" if last in _SIBILANT else "s" if last in _VOICELESS else "z")


def lookup(token: str, extra: Mapping[str, str] | None = None) -> tuple[str, str] | None:
    """``(phonemes, entry)`` for a token matching an entry of ``extra`` (first) or ``OVERRIDES``
    (module docstring), else None."""
    w = token.lower()
    for table in (extra or {}, OVERRIDES):
        if w in table:
            return table[w], w
        for suffix in ("'s", "’s", "s"):
            base = w.removesuffix(suffix)
            if base != w and base in table:
                return _plural(table[base]), base
    return None


def apply(tokens: Iterable[Any], extra: Mapping[str, str] | None = None) -> list[str]:
    """Set ``phonemes`` on every token whose ``text`` matches; return the entries used."""
    used: list[str] = []
    for t in tokens:
        hit = lookup(t.text, extra)
        if hit:
            t.phonemes, entry = hit
            used.append(entry)
    return used
