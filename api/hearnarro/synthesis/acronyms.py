"""How an all-caps token is read aloud: spoken as a word ("NASA") or spelled ("C E O")
(SYN-4, ING-6). Pure data and functions; the Kokoro backend applies them to misaki tokens.

**All-caps context first** (``caps_fold_spans``, applied to the whole segment before any
per-token decision). A token is *caps* (``is_caps``) when it has >= 2 letters, all upper case,
apostrophes and hyphens allowed inside (ERIC'S, LONG-TERM). A segment is an all-caps context
(a heading, an emphasized run) when it has >= 2 caps tokens in a row, or >= 2 word tokens of
which >= 60 % are caps, or is a single word that is caps ("FOREWORD"). In that context every caps
token is case-folded to a normal word for G2P (``fold_caps``: "ERIC'S" -> "Eric's", first
letter kept upper so names stay names), except tokens whose letters (before any apostrophe) are
in ``SPELLED`` or ``SPOKEN``, are defined by the document, or have no vowel (NFL, MVP): those keep
the per-token decision below. Folding keeps the length, so char spans are unchanged. Outside a
caps context nothing is folded ("the CEO said", "a TED talk").

A token is an acronym candidate when it is two or more ASCII capital letters and nothing else
(``is_acronym``). ``decide`` settles it in this order; the first rule that applies wins:

1. **Overrides** (``SPOKEN``, ``SPELLED`` below): fixed readings for common tokens.
2. **Collocations** (``COLLOCATIONS``): the token followed by a given word ("TED talk" spoken,
   "SAT score" spelled).
3. **Document definition**: the document defines the token, e.g. "Transferable Erosion Deposit
   (TED)" (``SynthContext.acronyms``, found at ingestion). A defined token is an initialism
   and is spelled, unless it has >= 4 letters and is ``pronounceable`` (NASA-like): spoken.
4. **Lexicon**: the lowercase form is a word in the backend's pronunciation lexicon: spoken.
5. **Heuristic** (``pronounceable``): spoken if >= 3 letters, contains a vowel (A E I O U Y),
   has no run of 3+ consonants, a 3-letter token is consonant-vowel-consonant (TED, not EPA),
   and a token that starts with two consonants starts with an English onset (ST, PL, ...,
   not FD or NB). Otherwise spelled.

An acronym with a possessive or plural suffix ("CEO's", "PDFs"; ``split_suffix``) is decided on
its letters; the suffix is voiced after the last sound (``suffix_phonemes``: "s" after a
voiceless consonant, "ᵻz" after a sibilant, else "z") and joins the last letter when spelled.

A mixed-case token whose tail is a run of two or more capitals after a lower-case letter
("OpenAI", "GenAI", "xAI", "OpenAI's"; ``split_camel_acronym``) is read as its word part on the
normal pronunciation tiers followed by the capital run decided like any acronym ("open A I").
Ordinary camel case ("iPhone", "YouTube") does not match and is left alone.

Spelling (``spell_phonemes``) gives one phoneme string per letter, all stresses secondary and
the last one primary, which concatenated is exactly misaki's own letter spelling; the backend
emits one token per letter so each letter has its own duration, while the word timestamp still
spans the original token (char offsets unchanged).

The override, respelling and collocation tables are plain data: users can extend them by adding entries here
(keep the two override sets disjoint and upper case).
"""

from __future__ import annotations

import itertools
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass

# Spoken as words. Organisations and terms read as words even though no general lexicon may
# list them, or where a lexicon entry would be missing or spelled. TED is deliberately absent:
# the lexicon speaks it, a document that defines it gets it spelled, and "TED talk" is a
# collocation below.
SPOKEN: frozenset[str] = frozenset(
    {
        # organisations
        "NASA", "NIST", "NATO", "UNESCO", "UNICEF", "OPEC", "FIFA", "IKEA", "NAFTA", "SWAT",
        "POTUS",
        # computing terms read as words
        "JSON", "RAM", "ROM",
        # words that started as acronyms
        "LASER", "SCUBA", "ASAP",
    }
)  # fmt: skip

# Spoken tokens whose sound no lexicon has: an ordinary word that sounds the same, looked up
# in the backend's lexicon instead of guessing (the g2p predictor reads "json" as "son").
RESPELL: dict[str, str] = {"JSON": "Jason"}

# Spelled letter by letter. Several are lexicon words (IT, US, OK) or look pronounceable (CEO,
# IBM), which is why they need an override.
SPELLED: frozenset[str] = frozenset(
    {
        # job titles and departments
        "CEO", "CFO", "CTO", "HR",
        # computing: formats, hardware, protocols ("S Q L" is the safer common reading)
        "PDF", "HTML", "CSS", "URL", "USB", "API", "SQL", "CPU", "GPU", "HTTP", "SSH", "IT",
        "PC", "TV", "DVD", "CD", "AI", "LLM", "NLP", "ML", "OS",
        # organisations and places
        "FBI", "CIA", "IBM", "UK", "US", "USA", "EU", "UN",
        # other
        "OK", "FYI",
    }
)  # fmt: skip

# (token, next word lowercased) -> spoken? A reading fixed by the word that follows.
COLLOCATIONS: dict[tuple[str, str], bool] = {
    # TED the conference is a word
    ("TED", "talk"): True,
    ("TED", "talks"): True,
    ("TED", "speaker"): True,
    ("TED", "conference"): True,
    # tests and scores are spelled, though "sat" and "act" are words
    ("SAT", "score"): False,
    ("SAT", "scores"): False,
    ("SAT", "test"): False,
    ("ACT", "score"): False,
    ("ACT", "test"): False,
    # medical scans and codes read as words
    ("CAT", "scan"): True,
    ("PET", "scan"): True,
    ("PIN", "code"): True,
    ("ZIP", "code"): True,
    ("MAC", "address"): True,
}

VOWELS = frozenset("AEIOUY")
ONSETS = frozenset(
    {"BL", "BR", "CH", "CL", "CR", "DR", "FL", "FR", "GL", "GR", "KN", "PH", "PL", "PR", "SC",
     "SH", "SK", "SL", "SM", "SN", "SP", "ST", "SW", "TH", "TR", "TW", "WH", "WR"}
)  # fmt: skip


@dataclass(frozen=True)
class Decision:
    spoken: bool
    reason: str  # "override" | "collocation" | "definition" | "lexicon" | "heuristic"


def is_acronym(token: str) -> bool:
    return len(token) >= 2 and token.isascii() and token.isalpha() and token.isupper()


def pronounceable(word: str) -> bool:
    """Rule 5 of the module docstring."""
    w = word.upper()
    if len(w) < 3 or not any(c in VOWELS for c in w):
        return False
    run = 0
    for c in w:
        run = 0 if c in VOWELS else run + 1
        if run >= 3:
            return False
    if len(w) == 3:
        return w[0] not in VOWELS and w[1] in VOWELS and w[2] not in VOWELS
    if w[0] not in VOWELS and w[1] not in VOWELS:
        return w[:2] in ONSETS
    return True


def decide(
    word: str,
    *,
    next_word: str | None = None,
    definitions: Mapping[str, str] | None = None,
    in_lexicon: Callable[[str], bool] = lambda _w: False,
) -> Decision:
    """Spoken or spelled, and which rule decided (module docstring, rules 1-5)."""
    if word in SPOKEN:
        return Decision(True, "override")
    if word in SPELLED:
        return Decision(False, "override")
    if next_word is not None and (word, next_word.lower()) in COLLOCATIONS:
        return Decision(COLLOCATIONS[(word, next_word.lower())], "collocation")
    if definitions and word in definitions:
        return Decision(len(word) >= 4 and pronounceable(word), "definition")
    if in_lexicon(word):
        return Decision(True, "lexicon")
    return Decision(pronounceable(word), "heuristic")


def spell_phonemes(word: str, letters: Mapping[str, str]) -> list[str]:
    """One phoneme string per letter (``letters``: "C" -> "sˈi"); every stress secondary, the
    last one primary."""
    out = [letters[c].replace("ˈ", "ˌ") for c in word]
    for i in range(len(out) - 1, -1, -1):
        if "ˌ" in out[i]:
            head, _, tail = out[i].rpartition("ˌ")
            out[i] = head + "ˈ" + tail
            break
    return out


_WORD = re.compile(r"[A-Za-z]+(?:['’-][A-Za-z]+)*")
_CAPS = re.compile(r"[A-Z]+(?:['’-][A-Z]+)*")
_SUFFIX = re.compile(r"([A-Z]{2,})(['’][sS]|s)")
_CAMEL_TAIL = re.compile(r"([A-Za-z]*[a-z])([A-Z]{2,})(['’][sS])?")


def is_caps(token: str) -> bool:
    """>= 2 letters, all upper case; apostrophes and hyphens allowed inside."""
    return bool(_CAPS.fullmatch(token)) and sum(c.isalpha() for c in token) >= 2


def _keeps_decision(token: str, definitions: Mapping[str, str] | None) -> bool:
    core = re.split(r"['’]", token)[0]
    return (
        core in SPELLED
        or core in SPOKEN
        or bool(definitions and core in definitions)
        or not any(c in VOWELS for c in core)
    )


def caps_fold_spans(
    text: str, definitions: Mapping[str, str] | None = None
) -> list[tuple[int, int]]:
    """Char spans of the caps tokens to case-fold, or [] outside an all-caps context."""
    words = list(_WORD.finditer(text))
    caps = [is_caps(m.group()) for m in words]
    run = any(a and b for a, b in itertools.pairwise(caps))
    share = len(words) >= 2 and sum(caps) >= 0.6 * len(words)
    single = len(words) == 1 and caps[0]
    if not (run or share or single):
        return []
    return [
        m.span()
        for m, c in zip(words, caps, strict=True)
        if c and not _keeps_decision(m.group(), definitions)
    ]


def fold_caps(text: str, definitions: Mapping[str, str] | None = None) -> str:
    """``text`` with the caps-context tokens case-folded ("ERIC'S" -> "Eric's"); same length."""
    out = text
    for a, b in caps_fold_spans(text, definitions):
        out = out[:a] + text[a] + text[a + 1 : b].lower() + out[b:]
    return out


def split_suffix(token: str) -> tuple[str, str] | None:
    """("CEO", "'s") for "CEO's", ("PDF", "s") for "PDFs"; None if not an acronym + suffix."""
    m = _SUFFIX.fullmatch(token)
    return (m.group(1), m.group(2)) if m else None


def split_camel_acronym(token: str) -> tuple[str, str, str] | None:
    """("Open", "AI", "") for "OpenAI", ("Open", "AI", "'s") for "OpenAI's"; None when the token
    does not end in 2+ capitals after a lower-case letter ("iPhone", "NASA", "PDFs")."""
    m = _CAMEL_TAIL.fullmatch(token)
    return (m.group(1), m.group(2), m.group(3) or "") if m else None


def suffix_phonemes(last: str) -> str:
    """The plural/possessive ending after phonemes ``last``."""
    if last.endswith(("s", "z", "ʃ", "ʒ", "ʧ", "ʤ")):
        return "ᵻz"
    if last.endswith(("p", "t", "k", "f", "θ")):
        return "s"
    return "z"
