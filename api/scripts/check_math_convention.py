"""Check the spoken-maths expected texts against the reading convention (MATH-1..4).

The convention lives in ``math_convention.json`` next to this script (spec
``_agent/specs/m5-academic-reading.md`` section 3c); the phase-3 mathspeak symbol table
loads the same file, so the expected texts and the reader cannot drift apart.

Sources checked:
- every non-comment line of ``api/tests/fixtures/pdfs/formula_*.spoken.txt``
- every ``spoken`` field of ``api/hearnarro/evals/data/math_speech.jsonl``

Violations: a banned wording (``banned`` in the JSON), a raw maths symbol or Greek letter
left in the spoken text, an upper-case letter (spoken text is lower case), or "capital"
not followed by a Greek letter name. Exit status 1 when any violation is found.

Usage: ``python api/scripts/check_math_convention.py``
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
API = HERE.parent
CONVENTION = HERE / "math_convention.json"
FIXTURES = API / "tests" / "fixtures" / "pdfs"
DATASET = API / "hearnarro" / "evals" / "data" / "math_speech.jsonl"

# ASCII characters that must never reach the voice as written maths ("-" and "/" are left
# out: hyphenated words and "and/or" are prose).
ASCII_LEAKS = set("=+<>^_\\{}|~$")


def load_convention(path: Path = CONVENTION) -> dict:
    """Return the convention table as a dict."""
    return json.loads(path.read_text(encoding="utf-8"))


def symbol_chars(conv: dict) -> set[str]:
    """Every single non-ASCII character the convention names a wording for."""
    chars: set[str] = set(ASCII_LEAKS)
    for section in ("operators", "relations", "arrows", "logic_and_sets", "greek", "capital_greek"):
        for key in conv[section]:
            chars.update(ch for ch in key if ord(ch) > 127)
    return chars


def iter_lines() -> list[tuple[str, str, str]]:
    """Return (source, line id, spoken text) for both expected-text sources."""
    out: list[tuple[str, str, str]] = []
    for path in sorted(FIXTURES.glob("formula_*.spoken.txt")):
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if line.strip() and not line.startswith("#"):
                out.append((path.name, str(n), line))
    for line in DATASET.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            out.append((DATASET.name, row["id"], row["spoken"]))
    return out


def check(conv: dict, lines: list[tuple[str, str, str]]) -> list[str]:
    """Return one message per violation."""
    banned = [(re.compile(b["pattern"]), b) for b in conv["banned"]]
    chars = symbol_chars(conv)
    greek_names = "|".join(sorted(set(conv["capital_greek"].values())))
    capital = re.compile(rf"\b{conv['capital_greek_prefix']} (?!(?:{greek_names})\b)\w+")
    problems: list[str] = []
    for source, line_id, text in lines:
        where = f"{source}:{line_id}"
        for rx, rule in banned:
            m = rx.search(text)
            if m:
                problems.append(
                    f"{where}: banned '{m.group(0)}' (use {rule['use']}; {rule['why']})"
                )
        leaked = sorted({ch for ch in text if ch in chars})
        if leaked:
            problems.append(f"{where}: raw symbol(s) {' '.join(leaked)} left in spoken text")
        if text != text.lower():
            problems.append(f"{where}: upper-case letters (spoken text is lower case)")
        m = capital.search(text)
        if m:
            problems.append(f"{where}: '{m.group(0)}' is not a capital Greek letter")
    return problems


def main() -> int:
    conv = load_convention()
    lines = iter_lines()
    problems = check(conv, lines)
    for p in problems:
        print(p)
    print(
        f"checked {len(lines)} lines, {len(conv['banned'])} banned patterns: {len(problems)} violation(s)"
    )
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
