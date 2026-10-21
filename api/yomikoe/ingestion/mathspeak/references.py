"""MATH-4 prose rewrites: equation references and theorem-style openers (spec §3b, §3c).

``rewrite_references`` returns ``(start, end, spoken)`` triples over the input text; the caller
(``speak_segment``) maps each spoken string onto ``text[start:end]`` with the ``normalize``
formula, so offsets stay exact. Forms:

- ``Eq. (3)``, ``Eq. 3``, ``Equation (3)``, ``Eqn. (3)`` -> "equation 3"
- ``Eqs. 3–5``, ``Eqs. (3)–(5)``, ``Equations 3-5`` -> "equations 3 to 5"
- ``Eqs. (3) and (4)`` -> "equations 3 and 4"
- an opener at the start of the text (``Theorem 2.1``, ``Lemma 3``, ``Definition``, ``Proof``,
  ``Corollary``, ``Proposition``, with an optional number) followed by a capitalised word gets a
  comma, mapped onto the opener, so the voice pauses ("Theorem 2.1, Every bounded ...").
"""

from __future__ import annotations

import re

_N = r"\(?(\d+(?:\.\d+)*)\)?"
_PLURAL = r"(?:Eqs\.|Eqns\.|Equations)"
_SINGLE = r"(?:Eq\.|Eqn\.|Equation)"
_RANGE = re.compile(rf"\b{_PLURAL}\s*{_N}\s*[–—-]\s*{_N}")
_PAIR = re.compile(rf"\b{_PLURAL}\s*{_N}\s+and\s+{_N}")
_ONE = re.compile(rf"\b{_SINGLE}\s*(?:\((\d+(?:\.\d+)*)\)|(\d+(?:\.\d+)*)\b)")
_OPENER = re.compile(
    r"^(?:Theorem|Lemma|Definition|Proof|Corollary|Proposition|Remark|Example|Conjecture)"
    r"(?:[ \t]+\d+(?:\.\d+)*)?(?=[ \t]+[A-Z(])"
)


def rewrite_references(text: str) -> list[tuple[int, int, str]]:
    """Non-overlapping (start, end, spoken) rewrites of MATH-4 forms in ``text``, sorted."""
    out: list[tuple[int, int, str]] = []

    def add(start: int, end: int, spoken: str) -> None:
        if not any(s < end and start < e for s, e, _ in out):
            out.append((start, end, spoken))

    for m in _RANGE.finditer(text):
        add(m.start(), m.end(), f"equations {m.group(1)} to {m.group(2)}")
    for m in _PAIR.finditer(text):
        add(m.start(), m.end(), f"equations {m.group(1)} and {m.group(2)}")
    for m in _ONE.finditer(text):
        add(m.start(), m.end(), f"equation {m.group(1) or m.group(2)}")
    opener = _OPENER.match(text)
    if opener:
        add(0, opener.end(), opener.group(0) + ",")
    return sorted(out)
