"""MATH-3 symbol table, loaded from the reading convention (spec §3c, D36).

The wordings are not written here: they are read from ``api/scripts/math_convention.json``, the
machine copy of spec §3c that ``api/scripts/check_math_convention.py`` checks the expected texts
against, so the reader and the expected texts cannot drift. Only character classes the JSON does
not list (Unicode script digits, combining accents, letter-like capitals) are defined below.

Units and chemical formulas in running text are rewritten by ``rewrite_units`` (prefix word plus
unit word, US spelling, plural unless the value is 1; element symbols letter by letter with digit
counts). ``°C`` stays with the ING-6 degree rule (``_DEGREES`` in ``normalize.py``).
"""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Any

CONVENTION_PATH = Path(__file__).resolve().parents[3] / "scripts" / "math_convention.json"


def _load() -> dict[str, Any]:
    data: dict[str, Any] = json.loads(CONVENTION_PATH.read_text(encoding="utf-8"))
    return data


CONVENTION: dict[str, Any] = _load()


def _lead_symbol(key: str) -> str | None:
    """The symbol a descriptive key names: "→ (limit or tends)" -> "→", "≤" -> "≤"."""
    head = key.split(" ", 1)[0]
    return head if head and len(head) <= 2 and not head.isalnum() else None


def _symbols() -> dict[str, str]:
    out: dict[str, str] = {}
    for section in ("operators", "relations", "arrows", "logic_and_sets"):
        for key, word in CONVENTION[section].items():
            sym = key if " " not in key else _lead_symbol(key)
            if sym and sym not in out:
                out[sym] = word
    # Prose-only forms of keys whose first char is a bracket: "{a, b}" -> the set.
    out.setdefault("{", "the set")
    return out


SYMBOLS: dict[str, str] = _symbols()
GREEK: dict[str, str] = {
    **CONVENTION["greek"],
    **{
        k: f"{CONVENTION['capital_greek_prefix']} {v}"
        for k, v in CONVENTION["capital_greek"].items()
    },
}
UNITS: dict[str, str] = dict(CONVENTION["units"])
SI_PREFIXES: dict[str, str] = dict(CONVENTION["si_prefixes"])


def _functions() -> dict[str, str]:
    out: dict[str, str] = {}
    for key, word in CONVENTION["functions"].items():
        if "(" in key:
            continue  # "f(x) (single letter f)" is a rule, not a name
        for name in key.split(", "):
            out[name] = word
    return out


FUNCTIONS: dict[str, str] = _functions()  # sin -> sine, Var -> the variance of, 𝔼 -> e

# Characters the JSON does not list as keys: script digits, letter-like capitals, dots.
SUPERSCRIPTS = dict(zip("⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾ⁿⁱᵀ", "0123456789+-=()niT", strict=True))
SUBSCRIPTS = dict(zip("₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎ᵢⱼₖₙₜₘₓₐₑₒₚₛ", "0123456789+-=()ijkntmxaeops", strict=True))
ACCENTS = {
    "̂": "hat",
    "̄": "bar",
    "̅": "bar",
    "̃": "tilde",
    "̇": "dot",
    "̈": "double dot",
    "⃗": "vector",
}
LETTERLIKE = {"ℝ": "r", "ℕ": "n", "ℤ": "z", "ℚ": "q", "ℂ": "c", "𝔼": "e", "ℓ": "l"}
EXTRA = {
    "…": "dot dot dot",
    "⋯": "dot dot dot",
    "∗": "star",
    "⊤": "transpose",
    "°": "degrees",
    "%": "percent",
    "*": "star",
    "µ": "mu",  # the micro sign, read as the Greek letter it stands for
    "'": "prime",
    "‖": "the norm of",
    "⟨": "the inner product of",
}


def name_of(ch: str) -> str | None:
    """The §3c wording of one symbol, a Greek letter, a letter or a digit; None if unnamed."""
    if len(ch) != 1 and ch not in SYMBOLS:
        return None  # one character at a time (a word or an empty string has no name)
    if ch in SYMBOLS:
        return SYMBOLS[ch]
    if ch in GREEK:
        return GREEK[ch]
    if ch in LETTERLIKE:
        return LETTERLIKE[ch]
    if ch in EXTRA:
        return EXTRA[ch]
    if ch in FUNCTIONS:
        return FUNCTIONS[ch]
    if 0x1D400 <= ord(ch) <= 0x1D7FF:  # mathematical alphanumerics (𝑥, 𝐀, 𝟏): the plain letter
        plain = unicodedata.normalize("NFKC", ch)
        return name_of(plain) if plain != ch else None
    if ch in SUPERSCRIPTS:
        d = SUPERSCRIPTS[ch]
        return {"2": "squared", "3": "cubed", "T": "transpose"}.get(d, f"to the {d}")
    if ch in SUBSCRIPTS:
        return f"sub {SUBSCRIPTS[ch]}"
    if ch.isascii() and ch.isalpha():
        return ch.lower()
    if ch.isascii() and ch.isdigit():
        return ch
    return None


# --- units and chemistry in running text (MATH-3) ---------------------------------------------

_NO_UNIT = {"pm"}  # "5 pm" is a clock time (ING-6), not picometers


def _alt(words: list[str]) -> str:
    return "|".join(re.escape(w) for w in sorted(words, key=len, reverse=True))


_UNIT_RE = re.compile(
    rf"(?<![\w.])(?P<num>\d+(?:\.\d+)?)[ \t]?(?P<tok>(?P<pre>{_alt(list(SI_PREFIXES))})?"
    rf"(?P<unit>{_alt(list(UNITS))}))(?![\w])"
)
_ELEMENTS = {
    "H",
    "He",
    "Li",
    "Be",
    "B",
    "C",
    "N",
    "O",
    "F",
    "Ne",
    "Na",
    "Mg",
    "Al",
    "Si",
    "P",
    "S",
    "Cl",
    "Ar",
    "K",
    "Ca",
    "Sc",
    "Ti",
    "V",
    "Cr",
    "Mn",
    "Fe",
    "Co",
    "Ni",
    "Cu",
    "Zn",
    "Ga",
    "Ge",
    "As",
    "Se",
    "Br",
    "Kr",
    "Rb",
    "Sr",
    "Y",
    "Zr",
    "Nb",
    "Mo",
    "Tc",
    "Ru",
    "Rh",
    "Pd",
    "Ag",
    "Cd",
    "In",
    "Sn",
    "Sb",
    "Te",
    "I",
    "Xe",
    "Cs",
    "Ba",
    "La",
    "Ce",
    "Pr",
    "Nd",
    "Pm",
    "Sm",
    "Eu",
    "Gd",
    "Tb",
    "Dy",
    "Ho",
    "Er",
    "Tm",
    "Yb",
    "Lu",
    "Hf",
    "Ta",
    "W",
    "Re",
    "Os",
    "Ir",
    "Pt",
    "Au",
    "Hg",
    "Tl",
    "Pb",
    "Bi",
    "Po",
    "At",
    "Rn",
    "Fr",
    "Ra",
    "Ac",
    "Th",
    "Pa",
    "U",
    "Np",
    "Pu",
}
_CHEM_RE = re.compile(r"(?<![\w-])(?:[A-Z][a-z]?\d*){2,}(?![\w-])")
_CHEM_PART = re.compile(r"([A-Z][a-z]?)(\d*)")
_NOT_CHEM = {"CoV", "NaN"}


def unit_words(token: str, value: str = "2") -> str | None:
    """ "km" -> "kilometers" ("kilometer" when ``value`` is "1"); None for a non-unit."""
    m = _UNIT_RE.fullmatch(f"{value} {token}")
    if m is None or token in _NO_UNIT:
        return None
    pre, unit = m.group("pre") or "", m.group("unit")
    if not pre and len(unit) == 1:
        return None  # a bare "5 m" or "2 A" is too often a variable or a label
    word = UNITS[unit]
    if value in ("1", "1.0") and word.endswith("s") and word != "hertz":
        word = word[:-1]
    return SI_PREFIXES.get(pre, "") + word


def chemical_words(token: str) -> str | None:
    """ "H2O" -> "h 2 o", "NaCl" -> "n a c l"; None when the token is not a formula."""
    if token in _NOT_CHEM or not _CHEM_RE.fullmatch(token):
        return None
    parts = _CHEM_PART.findall(token)
    if any(el not in _ELEMENTS for el, _ in parts):
        return None
    if not any(n for _, n in parts) and not any(len(el) == 2 for el, _ in parts):
        return None  # "CPU", "US": capitals with no count and no two-letter element
    words: list[str] = []
    for el, n in parts:
        words.extend(el.lower())
        if n:
            words.append(n)
    return " ".join(words)


def rewrite_units(text: str) -> list[tuple[int, int, str]]:
    """(start, end, spoken) for every unit after a number and every chemical formula in ``text``."""
    out: list[tuple[int, int, str]] = []
    for m in _UNIT_RE.finditer(text):
        spoken = unit_words(m.group("tok"), m.group("num"))
        if spoken:
            out.append((m.start("tok"), m.end("tok"), spoken))
    for m in _CHEM_RE.finditer(text):
        spoken = chemical_words(m.group(0))
        if spoken and not any(s < m.end() and m.start() < e for s, e, _ in out):
            out.append((m.start(), m.end(), spoken))
    return sorted(out)
