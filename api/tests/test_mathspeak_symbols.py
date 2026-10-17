"""MATH-3: the symbol table is the §3c convention (math_convention.json), units, chemistry."""

from __future__ import annotations

import re

import pytest

from hearnarro.evals.suites.eval10_mathspeak import load_pairs
from hearnarro.ingestion.mathspeak import speak_segment
from hearnarro.ingestion.mathspeak.markup import markup_segment
from hearnarro.ingestion.mathspeak.structure import CLOSE
from hearnarro.ingestion.mathspeak.symbols import (
    CONVENTION,
    GREEK,
    SI_PREFIXES,
    UNITS,
    chemical_words,
    name_of,
    rewrite_units,
    unit_words,
)

SECTIONS = ("operators", "relations", "logic_and_sets", "greek")


@pytest.mark.parametrize("section", SECTIONS)
def test_math3_every_symbol_key_resolves_to_its_wording(section: str) -> None:
    for key, word in CONVENTION[section].items():
        if " " in key or len(key) > 2 or key.isalnum():
            continue
        if key == ":=":
            continue  # a digraph, lexed as one operator
        assert name_of(key) == word, key


def test_math3_capital_greek_take_capital() -> None:
    for key, word in CONVENTION["capital_greek"].items():
        assert name_of(key) == f"capital {word}"
    assert len(GREEK) == len(CONVENTION["greek"]) + len(CONVENTION["capital_greek"])


def test_math3_every_non_ascii_char_in_the_convention_has_a_name() -> None:
    for section, table in CONVENTION.items():
        if not isinstance(table, dict):
            continue
        for key in table:
            for ch in key:
                if not ch.isascii() and ch not in CLOSE:
                    assert name_of(ch) is not None, (section, key, ch)


def test_math3_units_and_prefixes_from_the_convention() -> None:
    assert UNITS == CONVENTION["units"] and SI_PREFIXES == CONVENTION["si_prefixes"]
    for token, words in {
        "km": "kilometers",
        "ms": "milliseconds",
        "μm": "micrometers",
        "kHz": "kilohertz",
        "MPa": "megapascals",
        "mol": "moles",
        "mg": "milligrams",
        "nm": "nanometers",
        "GHz": "gigahertz",
        "kN": "kilonewtons",
        "keV": "kiloelectronvolts",
    }.items():
        assert unit_words(token) == words
    assert unit_words("km", "1") == "kilometer"
    assert unit_words("kHz", "1") == "kilohertz"
    assert unit_words("m") is None and unit_words("pm") is None and unit_words("cat") is None
    assert rewrite_units("at 5 pm, a 5 m rope") == []


def test_math3_chemical_formulas_letter_by_letter_with_digits() -> None:
    assert chemical_words("H2O") == "h 2 o"
    assert chemical_words("CO2") == "c o 2"
    assert chemical_words("CH4") == "c h 4"
    assert chemical_words("NaCl") == "n a c l"
    for word in ("CPU", "US", "NaN", "Brno", "PhD", "LaTeX", "The"):
        assert chemical_words(word) is None, word
    out, _ = speak_segment("Water is H2O and 1 km.", [])
    assert out == "Water is h 2 o and 1 kilometer."


def _outputs() -> list[str]:
    out = []
    for pair in load_pairs():
        text, spans = markup_segment(pair["raw"], pair["block"])
        out.append(speak_segment(text, spans)[0])
    return out


def test_math3_no_banned_wording_in_any_dataset_output() -> None:
    banned = [re.compile(b["pattern"]) for b in CONVENTION["banned"]]
    for text in _outputs():
        lowered = text.lower()
        for pattern in banned:
            assert not pattern.search(lowered), (pattern.pattern, text)


def test_math3_no_non_ascii_left_in_spoken_maths() -> None:
    for pair in load_pairs():
        text, spans = markup_segment(pair["raw"], pair["block"])
        out, cmap = speak_segment(text, spans)
        for k, ch in enumerate(out):
            if any(s.start <= cmap[k] < s.end for s in spans):
                assert ch.isascii(), (pair["id"], out)
