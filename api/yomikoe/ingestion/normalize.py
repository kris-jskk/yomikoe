"""Stage 5 normalization for speech, with a char_map back to the source (subset of ING-6).

All-caps tokens are left as written: whether "TED" is spoken or "PDF" spelled is decided by
the synthesis backend (``yomikoe.synthesis.acronyms``, SYN-4), which has a pronunciation
lexicon and the document's acronym definitions (``yomikoe.ingestion.acronyms``).

Phone numbers and clock hours (ING-6, user decision of 2026-10-17 after hearing sampler
sentence 8, "Call 555-0123 between 9 and 5."): a phone number is spoken as digit groups, never
as a dash range, and a clock hour is spoken with "a.m." / "p.m." The meridiem is written
"a.m." / "p.m." because misaki reads "AM" as the word "am" and both dotted forms as letters
(``_agent/results/557_am_pm_probe.txt``); a lexicon override for "am" would break the verb.
When the meridiem is absent, it is inferred by a heuristic: in a segment containing a cue word
(call, open, opens, hours, office, available, reach), "between H1 and H2" or "from H1 to H2"
with H1 in 6..11 and H2 in 1..7, followed by the end of text, punctuation or a time word
(every, each, daily, on, weekdays, weekends, except, local, time), becomes "H1 a.m. ... H2
p.m.". Limits: the cue is looked for in the whole segment passed in, not a clause; a pair
outside the bounds ("from 7 to 9", "between 12 and 1", evening hours "from 6 to 11") or
followed by any other word ("from 9 to 5 Monday") is left as written; "from 9 a.m. to 5"
(one side explicit) gets the explicit side only; a time written without a meridiem ("9:30")
is not changed (misaki drops "9:30" as an unknown token; pre-existing).
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from yomikoe.ingestion.expansions import EXPANSIONS
from yomikoe.ingestion.math_symbols import (
    CONTEXT_NAMES,
    GREEK,
    LETTER_NAMES,
    SYMBOL_NAMES,
    VARIATION_SELECTORS,
)
from yomikoe.ingestion.models import GLYPH_BULLET_RE
from yomikoe.ingestion.profile import PROSE_DEFAULT, DocumentProfile

_LABEL = r"[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?"
# Lowercase only, so a missing space after a sentence end ("the end.So we") is not a domain.
_TLDS = r"com|org|net|io|ai|co|edu|gov|dev|app|me|us|uk|de|fr|ca|info|biz|tv|ly|so|xyz"
# "https:// host" and "www. host" (a PDF line break) still reach the host.
_SPACE_BEFORE_HOST = r"(?:\s(?=[\w-]+\.\w))?"

# Roman numerals I..XXXIX that label structure ("PART II", "World War II") are spoken as
# cardinals; without this the voice reads "II" as letters or a pronoun ("PART E").
_ROMAN_UP = r"(?:X{1,3}(?:IX|IV|V?I{0,3})|IX|IV|V?I{1,3}|V)"
_ROMAN = rf"(?:{_ROMAN_UP}|(?-i:{_ROMAN_UP.lower()}))"
_STRUCTURAL = (
    r"part|chapter|book|section|volume|vol\.|act|scene|appendix|war|phase|stage|step|level|tier"
)
_ROMAN_VALUES = {"I": 1, "V": 5, "X": 10}
_ONES = [
    "zero",
    "one",
    "two",
    "three",
    "four",
    "five",
    "six",
    "seven",
    "eight",
    "nine",
    "ten",
    "eleven",
    "twelve",
    "thirteen",
    "fourteen",
    "fifteen",
    "sixteen",
    "seventeen",
    "eighteen",
    "nineteen",
]
_TENS = {2: "twenty", 3: "thirty"}
# A heading that is a numeral alone ("II", "XIV.") or leads with one ("II. Making Money").
_HEADING_ROMAN = re.compile(rf"(?P<num>{_ROMAN})(?=\.?\s*$|\.\s)")
# A dash between two plain integers ("1–10", "pp. 10-12", "3 - 5") is a range, spoken "to";
# misaki drops "1–10" as an unknown token and reads "10-12" as "ten twelve". Not a range when
# the first number follows a letter, digit or ". , : / -" (identifiers, decimals, times) or
# the second continues into a digit, decimal or another dash-joined number (ISBNs, dates).
_RANGE = (
    r"(?P<range>(?<![\w.,:/-])\d{1,4}(?P<rsep>[–—-]| [–—-] )"
    r"(?=\d{1,4}(?![.,:]?\d| ?[–—-] ?\d)))"
)
# "=" between terms is spoken "equals" ("Happiness = Health + Wealth", "2+2=4"), as misaki
# already speaks "+" as "plus"; misaki drops a lone "=" and the whole token "2+2=4". Spaced:
# one or more spaces or tabs each side and a non-space on both sides on the same line.
# Unspaced: only between a number or single letter and a number or single letter ("x=5"),
# so URL fragments ("v=2htl-O1oDcI", "campaign=platform") stay as written. "==", "=>",
# "<=", ">=", "!=" are not operators here. "≠" is spoken "does not equal" the same way.
_OPERAND = r"(?:\d+(?:\.\d+)?|[A-Za-z])"
_EQUALS = (
    r"(?P<eqspaced>(?<=[^\s=<>!])[ \t]+(?P<eqs_op>[=≠])[ \t]+(?=[^\s=>]))"
    rf"|(?P<eqtight>(?<![\w.=<>!]){_OPERAND}(?P<eqt_op>[=≠])"
    rf"(?={_OPERAND}(?![\w=]|[.,]\d)))"
)
_EQUALS_WORDS = {"=": " equals ", "≠": " does not equal "}
# A phone number: digit groups joined by "-" or "." ending in a group of 3-4 then 4 digits
# ("555-0123", "1-800-555-0123", "555.123.4567"), or led by "+" or a parenthesised area code
# where spaces also join groups ("+44 20 7946 0958", "(415) 555-0123"). Two plain groups need
# exactly 3 then 4 digits, so "2019-2021" stays a range; a penultimate group of 3-4 digits
# and a last group of 4 keep dates ("17-10-2026", "2026-10-17"), IPs and ISBNs out.
_PHONE_PLAIN = r"(?:\d{1,4}(?:[-.]\d{1,4})*[-.]\d{3,4}|\d{3})[-.]\d{4}"
_PHONE_INTL = r"\+\d{1,3}(?:[ .-]\d{1,4})*[ .-]\d{3,4}[ .-]\d{4}"
_PHONE_PAREN = r"\(\d{1,4}\)[ .-]?\d{3,4}[ .-]\d{4}"
_PHONE = (
    rf"(?P<phone>(?:(?<![\w+]){_PHONE_INTL}|(?<![\w(]){_PHONE_PAREN}"
    rf"|(?<![\w.,:/+-]){_PHONE_PLAIN})(?![\w-]|[.,:]\d))"
)
# A clock hour with a meridiem: "9am", "9 am", "9 a.m.", "9AM", "9:30pm", "12:00 PM".
_CLOCK = (
    r"(?P<clock>(?<![\w.,:/])(?P<hh>1[0-2]|0?[1-9])(?::(?P<mm>[0-5]\d))?"
    r"(?P<csp>[ \t]?)(?P<mer>(?i:[ap]\.?m\.?))(?!\w))"
)
# An hour pair without a meridiem ("between 9 and 5", "from 8 to 4"); validated in code.
_HOUR_FOLLOW = (
    r"(?![.,:]?\d)(?=[ \t]*(?:$|[.;!?)]|,(?!\d)"
    r"|(?i:every|each|daily|on|weekdays|weekends|except|local|time)\b))"
)
_HOUR_PAIR = (
    r"(?P<hpair>\b(?P<pw>(?i:between|from))[ \t]+(?P<h1>\d{1,2})[ \t]+"
    rf"(?P<mw>(?i:and|to))[ \t]+(?P<h2>\d{{1,2}}){_HOUR_FOLLOW})"
)
_HOUR_CUE = re.compile(r"\b(?:call|open|opens|hours|office|available|reach)\b", re.IGNORECASE)
_PAIR_WORDS = {"between": "and", "from": "to"}
# A rating, a small integer over 10 or 100 ("2/10", "95/100"), is spoken "out of"; misaki
# reads "2/10" as "two ten". Kept narrow to stay clear of dates and fractions ("9/11", "1/2",
# "10/12/2020", "24/7"): numerator 0..100 without a leading zero and not after a letter,
# digit or "/", denominator exactly 10 or 100 and not followed by a word char or "/".
_RATING = r"(?P<rating>(?<![\w/])(?:100|[1-9]?\d)(?P<rslash>/)(?:100|10)(?![\w/]))"
# An asterisk with spaces or tabs on both sides and a non-space on both sides on the same
# line is multiplication ("Wealth * (Return on Investment)"), spoken "times"; misaki is
# silent on it. "**", footnote marks ("word*", "*word") and a leading "* " bullet stay.
_TIMES = r"(?P<times>(?<=[^\s*])[ \t]+\*[ \t]+(?=[^\s*]))"
# A degree sign after a number (ING-6, user verdict on sampler sentence 11, 2026-10-17):
# "40°C" / "40 °C" / "40° C" -> "40 degrees Celsius", "°F" -> "Fahrenheit", a bare "90°"
# (angles) -> "90 degrees"; "1°C" is singular. The number and any sign before it are copied
# as written; a "°" with no digit before it and a bare "40C" without the sign stay as written.
_DEGREES = (
    r"(?P<deg>(?<![\w.])(?P<dnum>\d+(?:\.\d+)?)(?P<dsp>[ \t]?)°"
    r"(?:[ \t]?(?P<dunit>[CF])(?![A-Za-z]))?)"
)
_DEGREE_UNITS = {"C": " Celsius", "F": " Fahrenheit", None: ""}


# A numeric bracket "[12]", "[3, 4]", "[12–14]" is a citation and is dropped. It is a
# mathematical interval instead, kept as written (ING-6; wording is MATH-2, M5), when it starts
# with 0 ("[0, 2]"), is directly preceded (optionally one space) by a maths operator or "(",
# or is followed by ")". Brackets holding a letter, a Greek letter or ∞, and half-open forms
# ("[0, 1)", "(0, 1]") never match the citation shape, so they are kept too.
_MATH_BEFORE = "×∈⊂⊆∪∩⊗=("
_CITATION = (
    rf"(?P<citation>(?<![{_MATH_BEFORE}]\s)(?<![{_MATH_BEFORE}])"
    r"\[(?!0)\d+(?:\s*[,–-]\s*\d+)*\](?!\)))"
)

# An author-year parenthetical (TERM-3; spec §2a pattern, the one ``profile`` counts), or a
# semicolon-separated list of them ("(Smith, 2019; Jones et al., 2020)"). Read or dropped by
# ``DocumentProfile.author_year_citations``.
_AY_ONE = r"(?:[A-Z][\w'’-]+(?: et al\.)?(?:,| and| &)?\s?)+,? \d{4}[a-z]?"
_AUTHOR_YEAR = rf"(?P<authyear>\({_AY_ONE}(?:;\s?{_AY_ONE})*\))"
# Academic abbreviations (TERM-4): a whole token from ``EXPANSIONS``, any case, not inside a
# word or a dotted run ("cliff", "e.gov").
_EXPANSION = (
    r"(?P<expand>(?<![\w.])(?i:"
    + "|".join(re.escape(k) for k in sorted(EXPANSIONS, key=len, reverse=True))
    + r")(?![\w]|\.\w))"
)
_EXPANSION_KEYS = {k.lower(): v for k, v in EXPANSIONS.items()}


_PATTERN = re.compile(
    rf"{_CITATION}"
    rf"|{_AUTHOR_YEAR}"
    rf"|{_EXPANSION}"
    r"|(?P<etal>\bet al\.)"
    r"|(?P<percent>\b\d+(?:\.\d+)?%)"
    rf"|(?P<url>(?:\bhttps?://{_SPACE_BEFORE_HOST}(?:www\.)?|\bwww\.{_SPACE_BEFORE_HOST})"
    r"[^\s/]+(?:/\S*)?)"
    rf"|(?P<email>(?<![\w.+-])[A-Za-z0-9._%+-]+@{_LABEL}(?:\.{_LABEL})*\.[A-Za-z]{{2,}}\b)"
    rf"|(?P<domain>(?<![\w@./:-])(?:{_LABEL}\.)+(?:{_TLDS})(?![\w-]|\.\w)(?:/\S*)?)"
    rf"|(?P<roman>(?i:\b(?P<kw>{_STRUCTURAL})[ \t]+)(?P<num>{_ROMAN})\b(?![-'’]?\w))"
    rf"|{_HOUR_PAIR}"
    rf"|{_DEGREES}"
    rf"|{_CLOCK}"
    rf"|{_PHONE}"
    rf"|{_RATING}"
    rf"|{_RANGE}"
    rf"|{_EQUALS}"
    rf"|{_TIMES}"
)
_URL_PREFIX = re.compile(r"(?:https?://\s?(?:www\.)?|www\.\s?)")
_URL_TRAILING = ".,;:!?)]}'\"”’"
_DROP_FOLLOWERS = ",.;:!?)"
# A path is spoken ("/a/b" -> " slash a slash b") only when it is short and plain.
_PATH_SEGMENT = re.compile(r"[A-Za-z0-9_-]+")
_PATH_MAX_SEGMENTS = 3
_PATH_MAX_CHARS = 30
_SPOKEN = {".": " dot ", "/": " slash ", "@": " at "}


def roman_value(numeral: str) -> int:
    """Value of a valid roman numeral made of I, V and X (either case)."""
    total = 0
    digits = [_ROMAN_VALUES[c] for c in numeral.upper()]
    for k, v in enumerate(digits):
        total += -v if k + 1 < len(digits) and digits[k + 1] > v else v
    return total


def number_words(n: int) -> str:
    """Cardinal words for 1..39 ("two", "fourteen", "twenty-one")."""
    if n < 20:
        return _ONES[n]
    tens, ones = divmod(n, 10)
    return _TENS[tens] + (f"-{_ONES[ones]}" if ones else "")


# MATH-1 fallback (ING-6): symbols read by name (table in ``math_symbols``).
_PAD_LEFT_AFTER = ")]}"
_PAD_RIGHT_BEFORE = "([{"
_ARROW_NEIGHBOURS = "-=<>"
_MINUS_LEFT = ")]}|∞"
_MINUS_RIGHT = "([{|∞√∑∫∂∇"
_GREEK_WORD_MIN = 3
# Something shaped like a markup tag or an angle-bracketed address ("<div>", "<h1>", "</p>",
# "<name at host dot com>" after pass one): its "<" and ">" are never relations.
_TAG = re.compile(r"</?[A-Za-z][A-Za-z0-9-]*(?:\s[^<>\n]*)?>")
# Function application (MATH-2 ClearSpeak "f of x"): a lone letter glued to "(" ("O(1)", "u(x, t)").
_APPLY_BEFORE = "([{"
_APPLY = re.compile(r"(?:^|[\s(\[{])[A-Za-z]\(")
_OF = " of "


def _applied(s: str, i: int) -> bool:
    """Whether the letter (or Greek letter) at ``s[i]`` stands alone and is glued to a "(".

    It must start the text or follow whitespace or an opening bracket (so the last letter of a
    word, "word(s)", "log(x)", or of a glued term, "2x(y)", "uθ(x)", is never applied), and the
    very next char must be "(" ("E (1)" is left as written).
    """
    if i + 1 >= len(s) or s[i + 1] != "(":
        return False
    return i == 0 or s[i - 1].isspace() or s[i - 1] in _APPLY_BEFORE


def _is_greek(ch: str) -> bool:
    return "\u0370" <= ch <= "\u03ff" or "\u1f00" <= ch <= "\u1fff"


def _in_greek_word(s: str, i: int) -> bool:
    """True when ``s[i]`` is part of a run of 3+ Greek characters (Greek prose, not maths)."""
    a = i
    while a > 0 and _is_greek(s[a - 1]):
        a -= 1
    b = i + 1
    while b < len(s) and _is_greek(s[b]):
        b += 1
    return b - a >= _GREEK_WORD_MIN


def _maths_position(s: str, i: int, tags: list[tuple[int, int]]) -> bool:
    """Whether a context symbol ("<", ">", "·", "⋅", "−") at ``s[i]`` is in a maths position."""
    ch = s[i]
    if ch in "<>" and any(a <= i < b for a, b in tags):
        return False
    prev = s[i - 1] if i > 0 else ""
    nxt = s[i + 1] if i + 1 < len(s) else ""
    if ch in "<>":
        if (prev and prev in _ARROW_NEIGHBOURS) or (nxt and nxt in _ARROW_NEIGHBOURS):
            return False
        if prev in (" ", "\t") and nxt in (" ", "\t"):
            return i >= 2 and not s[i - 2].isspace() and i + 2 < len(s) and not s[i + 2].isspace()
        return prev.isalnum() and nxt.isalnum() and (prev.isdigit() or nxt.isdigit())
    if ch == "·":
        return not (prev.isspace() and nxt.isspace())
    if ch == "−":
        a = i - 1
        while a >= 0 and s[a] in " \t":
            a -= 1
        b = i + 1
        while b < len(s) and s[b] in " \t":
            b += 1
        left = s[a] if a >= 0 else ""
        right = s[b] if b < len(s) else ""
        return (
            bool(left and right)
            and (left.isalnum() or left in _MINUS_LEFT)
            and (right.isalnum() or right in _MINUS_RIGHT)
        )
    return True  # "⋅" is always a dot operator


# A dash glued to the front of a number in a maths-bearing segment (ING-6, MATH-1; M5 listening
# sheet 2026-10-22, "(—0.670)"): em dash, en dash, minus sign or hyphen.
_UNARY_DASHES = "—–−-"


def _unary_minus(s: str, cmap: list[int]) -> tuple[str, list[int]]:
    """In a segment that carries maths, a dash immediately followed by a digit and preceded by
    "(", "[" or a space reads "minus " ("(—0.670)" -> "(minus 0.670)"). A dash after a space
    whose previous non-space character is a digit ("3 -5") and a dash between two digits
    ("2010—2015", the range rule) are left alone. Every char of "minus " maps to the dash."""
    out: list[str] = []
    omap: list[int] = []
    for i, ch in enumerate(s):
        if ch in _UNARY_DASHES and i > 0 and i + 1 < len(s) and s[i + 1].isdigit():
            prev = s[i - 1]
            before = s[:i].rstrip(" \t")
            if prev in "([" or (prev in " \t" and not before[-1:].isdigit()):
                out.extend("minus ")
                omap.extend([cmap[i]] * 6)
                continue
        out.append(ch)
        omap.append(cmap[i])
    return "".join(out), omap


def _speak_symbols(s: str, cmap: list[int]) -> tuple[str, list[int]]:
    """MATH-1 fallback over the pass-one output: symbols and Greek letters become their names.

        Each name maps every output char (and any space added around it) onto the symbol's source
        index, so the char map stays monotone and inside the token. A name is separated by a space
        from a letter, digit or closing bracket before it and from a letter, digit or opening bracket
        after it ("∈C∞" -> "in C infinity", "uθ" -> "u theta"); existing spaces are reused, so no
        double space is created. Variation selectors are removed; blackboard bold becomes the plain
        letter. "<", ">", "·", "−" are spoken only in a maths position (``_maths_position``: never
    inside a tag-shaped "<...>", never next to "-", "=", "<", ">"; a "−" with an operand on each
    side, spaces allowed, so "H = −∑ p" reads "H equals minus sum p"); a Greek
        letter inside a run of three or more Greek characters (a Greek word) is left as written.

        Function application (MATH-2 ClearSpeak "f of x"): a single Latin letter, or a Greek letter
        this pass names, that starts the text or follows whitespace or an opening bracket and is
        immediately followed by "(" gets " of " after it, mapped onto the letter; the parentheses
        stay and are silent ("O(1)" -> "O of (1)", "E(X, η)" -> "E of (X, eta)"). Without this
        misaki reads "O(1" as one word and keeps only the letter. A longer word ("log(x)",
        "word(s)"), a digit ("2(a)"), a letter ending a term ("uθ(x)") and "E (1)" are untouched.
    """
    if not _APPLY.search(s) and not any(
        c in SYMBOL_NAMES or c in CONTEXT_NAMES or c in LETTER_NAMES or c in VARIATION_SELECTORS
        for c in s
    ):
        return s, cmap
    out: list[str] = []
    omap: list[int] = []
    n = len(s)
    tags = [m.span() for m in _TAG.finditer(s)] if "<" in s else []
    for i, ch in enumerate(s):
        if ch in VARIATION_SELECTORS:
            continue
        if ch in LETTER_NAMES:
            out.append(LETTER_NAMES[ch])
            omap.append(cmap[i])
            continue
        name = None
        if ch in GREEK:
            name = None if _in_greek_word(s, i) else GREEK[ch]
        elif ch in SYMBOL_NAMES:
            name = SYMBOL_NAMES[ch]
        elif ch in CONTEXT_NAMES and _maths_position(s, i, tags):
            name = CONTEXT_NAMES[ch]
        if name is None:
            out.append(ch)
            omap.append(cmap[i])
            if ch.isascii() and ch.isalpha() and _applied(s, i):
                out.extend(_OF)
                omap.extend([cmap[i]] * len(_OF))
            continue
        j = i + 1
        while j < n and s[j] in VARIATION_SELECTORS:
            j += 1
        nxt = s[j] if j < n else ""
        left = bool(out) and (out[-1].isalnum() or out[-1] in _PAD_LEFT_AFTER)
        right = bool(nxt) and (nxt.isalnum() or nxt in _PAD_RIGHT_BEFORE)
        if ch in GREEK and _applied(s, i):
            words = (" " if left else "") + name + _OF
        else:
            words = (" " if left else "") + name + (" " if right else "")
        out.extend(words)
        omap.extend([cmap[i]] * len(words))
    return "".join(out), omap


def _in_math(
    start: int, end: int, profile: DocumentProfile, math_spans: Sequence[tuple[int, int]]
) -> bool:
    if profile.effective == "prose":
        return False
    return any(lo <= start and end <= hi for lo, hi in math_spans)


def normalize(
    text: str,
    *,
    heading: bool = False,
    profile: DocumentProfile = PROSE_DEFAULT,
    math_spans: Sequence[tuple[int, int]] = (),
    maths: bool = False,
) -> tuple[str, list[int]]:
    """Return (normalized_text, char_map) with len(char_map) == len(normalized_text).

    Bracket rule (ING-11, D40): under a ``prose`` profile every numeric bracket group is a
    citation and dropped (today's rule). Under ``math`` or ``mixed`` a group that lies inside a
    ``math_spans`` range (offsets into ``text``) is maths, an interval or a matrix, and is
    copied as written for mathspeak; outside maths only a group of citation shape is dropped.
    The default profile keeps every existing caller's output unchanged.

    One left-to-right pass over regex matches (citation, et al., percent, URL, e-mail,
    bare domain).
    Unmatched characters are copied with identity mapping. A rewritten token at input
    ``[start, start + L)`` with expansion ``E`` (length L') maps output char k to
    ``start + min(L - 1, k * L // L')``: monotone, inside the token, first char -> start
    and, when L' >= L, last char -> start + L - 1. A dropped citation emits nothing; if the
    output then ends in whitespace and the next input char is whitespace, punctuation or the
    end of text, that trailing output space is removed so no double space remains.

    Web addresses are spoken as a person reads them (``_emit_address``): the scheme and
    ``www.`` emit nothing, each ``.`` / ``@`` / ``/`` becomes " dot " / " at " / " slash "
    with every output char mapped onto that one source char, letters map to themselves, and
    a path longer than 3 segments or 30 chars (or with non-plain segments) is dropped.
    Trailing sentence punctuation after the address stays as text.

    A leading bullet (``GLYPH_BULLET_RE``: a glyph such as "•" or "→", or "-" "–" "—" "*"
    before a space) and the whitespace around it emit nothing, so a list item is spoken from
    its first word; numbered markers ("1." "a)") are kept and spoken.

    Roman numerals I..XXXIX (all upper or all lower case) after a structural word on the
    same line (part, chapter, book, section, volume, vol., act, scene, appendix, war, phase,
    stage, step, level, tier; any case) become cardinal words ("PART II" -> "Part two"); an
    all-caps keyword is title-cased letter for letter so it is not spelled out. "I" after a
    lowercase keyword followed by a lowercase word ("part I think") is the pronoun and is
    kept. When ``heading`` is true, a numeral that is the whole text ("II", "XIV.") or leads
    it before ". " ("II. Making Money") is converted too, except a bare "I". "Henry VIII"
    and "Mr. X" have no keyword and are untouched.

    A numeric range, two integers of 1..4 digits joined by "–", "—" or "-" (no spaces, or one
    space on each side), becomes "a to b" with " to " mapped onto the dash ("1–10" -> "1 to
    10", "5–10%" -> "5 to 10 percent"). Excluded: a first number after a letter, digit or
    ". , : / -" ("A-1", "COVID-19", "1.5-2", "9:00-10:00") and a second number followed by a
    digit, ". , :" plus digit, or another dash and number ("978-0-12-...", "2026-10-17").

    An equals sign between terms becomes " equals " ("≠" becomes " does not equal "): with
    spaces or tabs on both sides and a non-space on both sides on the same line, the spaces
    collapse into the expansion, which maps onto the spaces and the sign; with no spaces,
    only between a number or a single letter on each side ("x=5", "2+2=4"), the expansion
    maps onto the sign. "==", "=>", "<=", ">=", "!=", a sign at the start or end of a line,
    one-sided spacing ("x =5") and unspaced words ("key=value", "v=2htl") are untouched.

    A rating, an integer 0..100 (no leading zero, not after a letter, digit or "/") over
    exactly 10 or 100 (not followed by a word char or "/"), becomes "a out of b" with " out
    of " mapped onto the slash ("2/10" -> "2 out of 10"); "9/11", "1/2", "10/12/2020",
    "24/7" and "km/h" are untouched. A phone number (``_PHONE``) is spoken digit by digit,
    each digit mapped to itself and the space after it mapped to that digit, each run of
    separators becoming ", " mapped onto the run, "(" emitting nothing and "+" becoming
    "plus " ("555-0123" -> "5 5 5, 0 1 2 3"). A clock hour with a meridiem becomes "H a.m." /
    "H MM p.m." (":00" emits nothing, ":05" -> " oh 5"), the meridiem mapped onto the source
    space and letters; an inferred pair (module docstring) maps each inserted " a.m." /
    " p.m." onto the hour's last digit. Before a source ".", "a.m" / "p.m" is emitted without
    its last dot so the sentence period completes it. An asterisk with spaces or tabs and a non-space on both
    sides on the same line becomes " times ", mapped onto the spaces and the asterisk; "**",
    "word*", "*word", "3*4" and a leading "* " bullet are untouched.

    MATH-1 fallback (PRD MATH-1, "the symbols left to right by name"): after the pass above,
    ``_speak_symbols`` reads mathematical symbols and Greek letters by name from the table in
    ``yomikoe.ingestion.math_symbols`` ("ν > 0" -> "nu greater than 0", "∈R3" -> "in R3"),
    every output char of a name mapped onto the symbol. Structure (sub/superscripts, fractions,
    exponents, display equations) is not recovered here. Mathspeak (``yomikoe.ingestion.
    mathspeak``) never feeds its spoken maths back into this function: it calls ``normalize`` only
    on the prose between maths spans and splices the spoken maths in afterwards, so this pass
    names stray symbols in prose and never rewrites a word mathspeak produced.

    ``maths`` is True when the segment carries maths (an equation block, or prose between the
    maths ranges of a body segment, as ``mathspeak`` calls this): a dash glued to the front of
    a number then reads "minus" (``_unary_minus``; ING-6, MATH-1).
    """
    out: list[str] = []
    cmap: list[int] = []

    def _meridiem(letter: str, source: str, end: int) -> str:
        """ "a.m." / "p.m.", without the last dot when a source "." follows to complete it."""
        dot_follows = not source.endswith(".") and text[end : end + 1] == "."
        return f"{letter}.m" if dot_follows else f"{letter}.m."

    def emit(s: str, start: int, length: int) -> None:
        n = len(s)
        for k, ch in enumerate(s):
            out.append(ch)
            cmap.append(start + min(length - 1, k * length // n))

    def emit_char(i: int) -> None:
        for ch in _SPOKEN.get(text[i], text[i]):
            out.append(ch)
            cmap.append(i)

    def emit_address(start: int, end: int, kind: str) -> None:
        """Speak ``text[start:end]`` (a trimmed URL, e-mail or bare domain)."""
        token = text[start:end]
        i = start
        if kind == "url":
            prefix = _URL_PREFIX.match(token)
            i += prefix.end() if prefix else 0
        host_end = i
        while host_end < end and text[host_end] not in "/?#":
            host_end += 1
        for k in range(i, host_end):
            emit_char(k)
        path = text[host_end:end]
        if not path.startswith("/"):
            return
        segments = path.strip("/").split("/")
        if (
            len(segments) > _PATH_MAX_SEGMENTS
            or len(path) > _PATH_MAX_CHARS
            or not all(_PATH_SEGMENT.fullmatch(seg) for seg in segments)
        ):
            return
        for k in range(host_end, host_end + len(path.rstrip("/"))):
            emit_char(k)

    bullet = GLYPH_BULLET_RE.match(text)
    pos = bullet.end() if bullet else 0
    lead = _HEADING_ROMAN.match(text, pos) if heading else None
    if lead and lead.group("num").upper() != "I":
        emit(number_words(roman_value(lead.group("num"))), pos, lead.end() - pos)
        pos = lead.end()
    for m in _PATTERN.finditer(text, pos):
        for i in range(pos, m.start()):
            out.append(text[i])
            cmap.append(i)
        start, end = m.start(), m.end()
        kind = m.lastgroup
        token = m.group()
        suffix_start = end
        if kind == "citation" and _in_math(start, end, profile, math_spans):
            suffix_start = start  # maths, not a citation: copied as written
        elif kind == "citation":
            nxt = text[end] if end < len(text) else ""
            if out and out[-1].isspace() and (not nxt or nxt.isspace() or nxt in _DROP_FOLLOWERS):
                out.pop()
                cmap.pop()
        elif kind == "authyear" and _in_math(start, end, profile, math_spans):
            suffix_start = start  # maths, not a citation: copied as written
        elif kind == "authyear" and profile.author_year_citations == "skip":
            nxt = text[end] if end < len(text) else ""
            if out and out[-1].isspace() and (not nxt or nxt.isspace() or nxt in _DROP_FOLLOWERS):
                out.pop()
                cmap.pop()
        elif kind == "authyear":
            k = start + 1
            while k < end - 1:
                if token.startswith("et al.", k - start):
                    emit("et al", k, 6)
                    k += 6
                    continue
                ch = text[k]
                if ch == "&":
                    emit("and", k, 1)
                elif ch == ";":
                    out.append(",")
                    cmap.append(k)
                elif ch != ",":
                    out.append(ch)
                    cmap.append(k)
                k += 1
        elif kind == "expand":
            words = _EXPANSION_KEYS[token.lower()]
            before = "".join(out).rstrip()
            if token[0].isupper() and (not before or before[-1] in ".!?"):
                words = words[0].upper() + words[1:]
            if token.endswith(".") and not text[end:].strip():
                words += "."  # the abbreviation's dot also ends the text
            emit(words, start, len(token))
        elif kind == "etal":
            emit("et al", start, len(token))
        elif kind == "percent":
            emit(token[:-1] + " percent", start, len(token))
        elif kind in ("url", "email", "domain"):
            trimmed = token.rstrip(_URL_TRAILING)
            suffix_start = start + len(trimmed)
            emit_address(start, suffix_start, kind)
        elif kind == "roman":
            kw, num = m.group("kw"), m.group("num")
            nxt = text[end : end + 2]
            if (
                num in ("I", "i")
                and kw[0].islower()
                and len(nxt) == 2
                and nxt[0] == " "
                and (nxt[1].islower())
            ):
                emit(token, start, len(token))  # "part I think": the pronoun
            else:
                kw_out = kw.capitalize() if kw.isupper() and len(kw) > 1 else kw
                for k, ch in enumerate(kw_out):
                    out.append(ch)
                    cmap.append(start + k)
                num_start = m.start("num")
                for i in range(start + len(kw), num_start):
                    out.append(text[i])
                    cmap.append(i)
                emit(number_words(roman_value(num)), num_start, len(num))
        elif kind == "range":
            sep_start = m.start("rsep")
            for i in range(start, sep_start):
                out.append(text[i])
                cmap.append(i)
            emit(" to ", sep_start, end - sep_start)  # the second number is matched on its own
        elif kind == "phone":
            k = start
            while k < end:
                ch = text[k]
                if ch == "+":
                    emit("plus ", k, 1)
                elif ch.isdigit():
                    out.append(ch)
                    cmap.append(k)
                    if k + 1 < end and text[k + 1].isdigit():
                        out.append(" ")
                        cmap.append(k)
                elif ch != "(":
                    run = k
                    while k + 1 < end and not text[k + 1].isdigit():
                        k += 1
                    if out and out[-1].isdigit():
                        emit(", ", run, k + 1 - run)
                k += 1
        elif kind == "clock":
            hh_end = m.end("hh")
            for i in range(start, hh_end):
                out.append(text[i])
                cmap.append(i)
            mm = m.group("mm")
            if mm and mm != "00":
                if mm[0] == "0":
                    emit(" oh ", hh_end, 2)
                    out.append(mm[1])
                    cmap.append(hh_end + 2)
                else:
                    emit(" ", hh_end, 1)
                    for i in range(hh_end + 1, hh_end + 3):
                        out.append(text[i])
                        cmap.append(i)
            mer = m.group("mer")
            sp = m.start("csp")
            emit(" " + _meridiem(mer[0].lower(), mer, end), sp, end - sp)
        elif kind == "hpair":
            h1, h2 = int(m.group("h1")), int(m.group("h2"))
            if (
                _PAIR_WORDS[m.group("pw").lower()] == m.group("mw").lower()
                and 6 <= h1 <= 11
                and 1 <= h2 <= 7
                and _HOUR_CUE.search(text)
            ):
                h1_end, h2_end = m.end("h1"), m.end("h2")
                for i in range(start, h1_end):
                    out.append(text[i])
                    cmap.append(i)
                emit(" a.m.", h1_end - 1, 1)
                for i in range(h1_end, h2_end):
                    out.append(text[i])
                    cmap.append(i)
                emit(" " + _meridiem("p", "", end), h2_end - 1, 1)
            else:
                suffix_start = start  # not an hour pair: copied as written
        elif kind == "rating":
            slash = m.start("rslash")
            for i in range(start, slash):
                out.append(text[i])
                cmap.append(i)
            emit(" out of ", slash, 1)
            suffix_start = slash + 1  # the denominator is copied as written
        elif kind == "deg":
            num_end = m.end("dnum")
            for i in range(start, num_end):
                out.append(text[i])
                cmap.append(i)
            noun = " degree" if m.group("dnum") == "1" else " degrees"
            emit(noun + _DEGREE_UNITS[m.group("dunit")], num_end, end - num_end)
        elif kind == "times":
            emit(" times ", start, end - start)
        elif kind == "eqspaced":
            emit(_EQUALS_WORDS[m.group("eqs_op")], start, end - start)
        elif kind == "eqtight":
            op = m.start("eqt_op")
            for i in range(start, op):
                out.append(text[i])
                cmap.append(i)
            emit(_EQUALS_WORDS[text[op]], op, 1)
        for i in range(suffix_start, end):
            out.append(text[i])
            cmap.append(i)
        pos = end
    for i in range(pos, len(text)):
        out.append(text[i])
        cmap.append(i)
    joined = "".join(out)
    if maths:  # the segment carries maths: an equation block or a body segment with a range
        joined, cmap = _unary_minus(joined, cmap)
    return _speak_symbols(joined, cmap)
