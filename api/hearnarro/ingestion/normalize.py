"""Stage 5 normalization for speech, with a char_map back to the source (subset of ING-6).

All-caps tokens are left as written: whether "TED" is spoken or "PDF" spelled is decided by
the synthesis backend (``hearnarro.synthesis.acronyms``, SYN-4), which has a pronunciation
lexicon and the document's acronym definitions (``hearnarro.ingestion.acronyms``).
"""

from __future__ import annotations

import re

from hearnarro.ingestion.models import GLYPH_BULLET_RE

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
# A rating, a small integer over 10 or 100 ("2/10", "95/100"), is spoken "out of"; misaki
# reads "2/10" as "two ten". Kept narrow to stay clear of dates and fractions ("9/11", "1/2",
# "10/12/2020", "24/7"): numerator 0..100 without a leading zero and not after a letter,
# digit or "/", denominator exactly 10 or 100 and not followed by a word char or "/".
_RATING = r"(?P<rating>(?<![\w/])(?:100|[1-9]?\d)(?P<rslash>/)(?:100|10)(?![\w/]))"
# An asterisk with spaces or tabs on both sides and a non-space on both sides on the same
# line is multiplication ("Wealth * (Return on Investment)"), spoken "times"; misaki is
# silent on it. "**", footnote marks ("word*", "*word") and a leading "* " bullet stay.
_TIMES = r"(?P<times>(?<=[^\s*])[ \t]+\*[ \t]+(?=[^\s*]))"


_PATTERN = re.compile(
    r"(?P<citation>\[\d+(?:\s*[,–-]\s*\d+)*\])"
    r"|(?P<etal>\bet al\.)"
    r"|(?P<percent>\b\d+(?:\.\d+)?%)"
    rf"|(?P<url>(?:\bhttps?://{_SPACE_BEFORE_HOST}(?:www\.)?|\bwww\.{_SPACE_BEFORE_HOST})"
    r"[^\s/]+(?:/\S*)?)"
    rf"|(?P<email>(?<![\w.+-])[A-Za-z0-9._%+-]+@{_LABEL}(?:\.{_LABEL})*\.[A-Za-z]{{2,}}\b)"
    rf"|(?P<domain>(?<![\w@./:-])(?:{_LABEL}\.)+(?:{_TLDS})(?![\w-]|\.\w)(?:/\S*)?)"
    rf"|(?P<roman>(?i:\b(?P<kw>{_STRUCTURAL})[ \t]+)(?P<num>{_ROMAN})\b(?![-'’]?\w))"
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


def normalize(text: str, *, heading: bool = False) -> tuple[str, list[int]]:
    """Return (normalized_text, char_map) with len(char_map) == len(normalized_text).

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
    "24/7" and "km/h" are untouched. An asterisk with spaces or tabs and a non-space on both
    sides on the same line becomes " times ", mapped onto the spaces and the asterisk; "**",
    "word*", "*word", "3*4" and a leading "* " bullet are untouched.
    """
    out: list[str] = []
    cmap: list[int] = []

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
        if kind == "citation":
            nxt = text[end] if end < len(text) else ""
            if out and out[-1].isspace() and (not nxt or nxt.isspace() or nxt in _DROP_FOLLOWERS):
                out.pop()
                cmap.pop()
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
        elif kind == "rating":
            slash = m.start("rslash")
            for i in range(start, slash):
                out.append(text[i])
                cmap.append(i)
            emit(" out of ", slash, 1)
            suffix_start = slash + 1  # the denominator is copied as written
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
    return "".join(out), cmap
