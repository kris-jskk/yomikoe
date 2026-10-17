"""Acronym definitions found in a document's text (stage 5, ING-6).

Two patterns, first definition per acronym wins:

- ``<words> (ACR)``: the words just before the parenthesis spell ACR by their initials,
  e.g. "Transferable Erosion Deposit (TED)", "Department of Energy (DOE)";
- ``ACR (<words>)``: the reverse, e.g. "ZTA (Zero Trust Architecture)".

Initials match left to right: each letter of ACR is the first letter of the next word; the
first word is capitalized; other words are capitalized, or a minor word ("of", "and", "the",
...) which may supply a letter or be skipped. "Figure 2 (left)" and "TED (left)" do not match.
The result (``{ACR: expansion}``) is stored on the document (``documents.acronyms_json``) and
handed to the synthesis backend, which spells a defined short acronym (SYN-4).
"""

from __future__ import annotations

import re
from collections.abc import Iterable

MINOR = frozenset(
    {"a", "an", "and", "as", "at", "by", "for", "from", "in", "into", "of", "on", "or", "the",
     "to", "with"}
)  # fmt: skip
_WORD = re.compile(r"[A-Za-z][A-Za-z'’-]*$")
_FORWARD = re.compile(r"\(([A-Z]{2,})\)")
_REVERSE = re.compile(r"\b([A-Z]{2,})\s+\(([^()]{3,120})\)")


def _matches(words: list[str], acr: str) -> bool:
    """Do ``words`` spell ``acr`` by initials (module docstring rule)?"""
    if not words or not words[0][0].isupper() or words[0][0] != acr[0]:
        return False

    def go(i: int, j: int) -> bool:
        if i == len(words):
            return j == len(acr)
        w = words[i]
        minor = w.lower() in MINOR
        if (
            j < len(acr)
            and w[0].upper() == acr[j]
            and (w[0].isupper() or minor)
            and go(i + 1, j + 1)
        ):
            return True
        return minor and i > 0 and go(i + 1, j)

    return go(0, 0)


def _forward(text: str, m: re.Match[str]) -> str | None:
    acr = m.group(1)
    before = text[max(0, m.start() - 300) : m.start()].split()
    words: list[str] = []
    for w in reversed(before[-(2 * len(acr) + 2) :]):
        if not _WORD.match(w):
            break
        words.insert(0, w)
    for n in range(len(acr), len(words) + 1):
        window = words[-n:]
        if _matches(window, acr):
            return " ".join(window)
    return None


def _reverse(m: re.Match[str]) -> str | None:
    acr, inner = m.group(1), m.group(2).strip()
    words = inner.split()
    if all(_WORD.match(w) for w in words) and _matches(words, acr):
        return " ".join(words)
    return None


def find_definitions(text: str) -> dict[str, str]:
    """``{ACR: expansion}`` for every definition in ``text``, first one per ACR."""
    found: list[tuple[int, str, str]] = []
    for m in _FORWARD.finditer(text):
        exp = _forward(text, m)
        if exp:
            found.append((m.start(), m.group(1), exp))
    for m in _REVERSE.finditer(text):
        exp = _reverse(m)
        if exp:
            found.append((m.start(), m.group(1), exp))
    out: dict[str, str] = {}
    for _, acr, exp in sorted(found):
        out.setdefault(acr, exp)
    return out


def document_definitions(texts: Iterable[str]) -> dict[str, str]:
    """``find_definitions`` over a document's merged block texts, in reading order."""
    out: dict[str, str] = {}
    for t in texts:
        for acr, exp in find_definitions(t).items():
            out.setdefault(acr, exp)
    return out
