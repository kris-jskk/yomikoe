"""SYN-4 / ING-6: the backend decides how an all-caps token is read (spoken as a word or
spelled letter by letter). Pure functions; no model needed."""

from __future__ import annotations

import pytest

from hearnarro.synthesis.acronyms import (
    COLLOCATIONS,
    RESPELL,
    SPELLED,
    SPOKEN,
    caps_fold_spans,
    decide,
    fold_caps,
    is_acronym,
    is_caps,
    pronounceable,
    spell_phonemes,
    split_suffix,
    suffix_phonemes,
)
from hearnarro.synthesis.backend import SynthContext
from hearnarro.synthesis.kokoro_backend import _Timed, word_timestamps

LEXICON = {"ted", "nasa", "nist", "the", "end", "it", "us"}


def in_lex(word: str) -> bool:
    return word.lower() in LEXICON


def test_syn4_override_sets_are_disjoint_and_upper() -> None:
    assert not SPOKEN & SPELLED
    assert all(w.isupper() and w.isalpha() for w in SPOKEN | SPELLED)
    assert {"NASA", "NIST", "UNESCO", "JSON", "IKEA"} <= SPOKEN
    assert {"CEO", "PDF", "HTML", "USB", "FBI", "SQL", "GPU", "AI", "UK", "IBM"} <= SPELLED


def test_syn4_respellings_are_spoken_words() -> None:
    assert RESPELL["JSON"] == "Jason"
    assert set(RESPELL) <= SPOKEN and all(w.isalpha() for w in RESPELL.values())


@pytest.mark.parametrize(
    ("token", "expected"),
    [("TED", True), ("PDF", True), ("A", False), ("I", False), ("Ted", False), ("PDFs", False)],
)
def test_syn4_is_acronym(token: str, expected: bool) -> None:
    assert is_acronym(token) is expected


@pytest.mark.parametrize(
    ("word", "spoken", "reason"),
    [
        ("NASA", True, "override"),
        ("JSON", True, "override"),
        ("CEO", False, "override"),
        ("PDF", False, "override"),
        ("SQL", False, "override"),
        ("IT", False, "override"),  # in the lexicon as "it", but the override wins
        ("TED", True, "lexicon"),
        ("END", True, "lexicon"),
        ("ZORBO", True, "heuristic"),  # vowel, no 3-consonant run
        ("GDPR", False, "heuristic"),  # no vowel
        ("ISBN", False, "heuristic"),  # SBN run
        ("FDA", False, "heuristic"),  # FD is not an English onset
        ("EPA", False, "heuristic"),  # 3 letters must be consonant-vowel-consonant
        ("ZIG", True, "heuristic"),
    ],
)
def test_syn4_decide_without_context(word: str, spoken: bool, reason: str) -> None:
    d = decide(word, in_lexicon=in_lex)
    assert (d.spoken, d.reason) == (spoken, reason)


def test_syn4_collocations_beat_definitions_and_lexicon() -> None:
    assert COLLOCATIONS[("TED", "talk")] is True
    assert decide("TED", next_word="talk", in_lexicon=in_lex).reason == "collocation"
    defs = {"TED": "Transferable Erosion Deposit"}
    d = decide("TED", next_word="talks", definitions=defs, in_lexicon=in_lex)
    assert (d.spoken, d.reason) == (True, "collocation")
    d = decide("SAT", next_word="score", in_lexicon=lambda w: w.lower() == "sat")
    assert (d.spoken, d.reason) == (False, "collocation")


def test_syn4_document_definition_spells_short_initialisms() -> None:
    defs = {"TED": "Transferable Erosion Deposit", "ZTA": "Zero Trust Architecture"}
    assert decide("TED", definitions=defs, in_lexicon=in_lex) == decide(
        "TED", next_word="values", definitions=defs, in_lexicon=in_lex
    )
    d = decide("TED", definitions=defs, in_lexicon=in_lex)
    assert (d.spoken, d.reason) == (False, "definition")
    assert decide("ZTA", definitions=defs).spoken is False
    # defined but pronounceable with >= 4 letters: spoken (NASA-like)
    d = decide("ZORBO", definitions={"ZORBO": "Zonal Orbit Observatory"})
    assert (d.spoken, d.reason) == (True, "definition")
    # without the definition TED is a lexicon word again
    assert decide("TED", definitions={}, in_lexicon=in_lex).spoken is True


def test_syn4_synth_context_carries_definitions() -> None:
    ctx = SynthContext(acronyms={"TED": "Transferable Erosion Deposit"}, document_id=7)
    assert ctx.acronyms["TED"].startswith("Transferable")
    assert SynthContext(acronyms={}).document_id is None


@pytest.mark.parametrize(
    ("word", "expected"),
    [("NASA", True), ("NIST", True), ("SCUBA", True), ("TED", True), ("HTML", False),
     ("CEO", False), ("PDF", False), ("IKEA", True), ("NBA", False), ("ab", False)],
)  # fmt: skip
def test_syn4_pronounceable(word: str, expected: bool) -> None:
    assert pronounceable(word) is expected


def test_syn4_spell_phonemes_one_per_letter_last_stress_primary() -> None:
    letters = {"C": "sˈi", "E": "ˈi", "O": "ˈO"}
    assert spell_phonemes("CEO", letters) == ["sˌi", "ˌi", "ˈO"]
    assert "".join(spell_phonemes("CEO", letters)) == "sˌiˌiˈO"  # misaki get_NNP form


def test_syn1_spelled_letters_fold_into_one_word_timestamp() -> None:
    text = "The CEO left"
    timed = [
        _Timed("The", 0, 100),
        _Timed("C", 120, 200),
        _Timed("E", 200, 260),
        _Timed("O", 260, 400),
        _Timed("left", 420, 600),
    ]
    ts = word_timestamps(text, timed, duration_ms=700)
    assert [(t.word, t.start_ms, t.end_ms, t.char_start, t.char_end) for t in ts] == [
        ("The", 0, 100, 0, 3),
        ("CEO", 120, 400, 4, 7),
        ("left", 420, 600, 8, 12),
    ]


# --- SYN-4: all-caps context (headings, emphasized runs) -----------------------------------


@pytest.mark.parametrize(
    ("token", "caps"),
    [("ERIC'S", True), ("LONG-TERM", True), ("NOTE", True), ("I", False), ("Eric", False),
     ("CEO's", False), ("PDFs", False), ("#1", False)],
)  # fmt: skip
def test_syn4_is_caps(token: str, caps: bool) -> None:
    assert is_caps(token) is caps


@pytest.mark.parametrize(
    ("text", "folded"),
    [
        ("ERIC'S NOTE", "Eric's Note"),
        ("PART I: WEALTH", "Part I: Wealth"),  # never "P A R T"
        ("BUILDING WEALTH", "Building Wealth"),
        ("UNDERSTAND HOW WEALTH IS CREATED", "Understand How Wealth Is Created"),
        ("TWEETS AND TWEETSTORMS", "Tweets And Tweetstorms"),
        ("TRAP #1: LACK OF INTENTIONALITY", "Trap #1: Lack Of Intentionality"),
        ("DEAR READER,", "Dear Reader,"),
        ("LONG-TERM GAMES", "Long-term Games"),
        # one-word headings are words, unless SPELLED
        ("FOREWORD", "Foreword"),
        ("PREFACE", "Preface"),
        ("CONTENTS", "Contents"),
        ("SOURCES", "Sources"),
        ("PDF", "PDF"),
        # mixed: SPELLED stays, the caps run is folded
        ("The CEO read ERIC'S NOTE", "The CEO read Eric's Note"),
        ("WHY THE CEO LEFT", "Why The CEO Left"),
        # SPOKEN overrides and vowel-less tokens keep the per-token decision
        ("PARSE THE JSON", "Parse The JSON"),
        ("NFL MVP AWARDS", "NFL MVP Awards"),
        # outside a caps context nothing changes
        ("the CEO said", "the CEO said"),
        ("a TED talk", "a TED talk"),
        ("The NASA team met the FBI today.", "The NASA team met the FBI today."),
    ],
)
def test_syn4_caps_context_folds_heading_words(text: str, folded: str) -> None:
    out = fold_caps(text)
    assert out == folded
    assert len(out) == len(text)  # char spans unchanged


def test_syn4_caps_context_keeps_document_defined_acronym_spelled() -> None:
    defs = {"TED": "Transferable Erosion Deposit"}
    assert fold_caps("WHY TED VALUES FELL", defs) == "Why TED Values Fell"
    assert fold_caps("WHY TED VALUES FELL") == "Why Ted Values Fell"
    text = "WHY TED VALUES FELL"
    assert [text[a:b] for a, b in caps_fold_spans(text, defs)] == ["WHY", "VALUES", "FELL"]


@pytest.mark.parametrize(
    ("token", "split"),
    [("CEO's", ("CEO", "'s")), ("CEO’s", ("CEO", "’s")), ("PDFs", ("PDF", "s")),
     ("CEO'S", ("CEO", "'S")), ("NASA", None), ("Uber's", None), ("Is", None), ("PDF", None)],
)  # fmt: skip
def test_syn4_split_acronym_suffix(token: str, split: tuple[str, str] | None) -> None:
    assert split_suffix(token) == split


def test_syn4_suffix_phonemes_voicing() -> None:
    assert suffix_phonemes("ˈɛf") == "s"  # PDFs
    assert suffix_phonemes("ˈO") == "z"  # CEO's
    assert suffix_phonemes("ˈɛs") == "ᵻz"  # OSes
    assert suffix_phonemes("ˈeɪʧ") == "ᵻz"
