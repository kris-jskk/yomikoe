"""Abbreviation data for the stage-5 sentence splitter (ING-5).

Entries are lowercase and include the final period. A token matches when the last
whitespace-separated token of a sentence, with leading brackets and quotes stripped and
lowercased, equals an entry. Single capital letters (initials, maths variables) are not listed
here: segment.py handles them by context.

Three behaviours:

- ``non_terminal``: never ends a sentence; a split after it is always undone.
- ``before_number``: does not end a sentence when the next text starts with a digit or bracket
  ("No. 5", "Vol. 3", "pp. 12"); "no." is also an ordinary word, so a capital after it splits.
- ``may_end``: often ends a sentence ("... pears, etc. Then"); the split is undone only when
  the next text does not start with a capital letter.

A document may extend the defaults (``DEFAULT_ABBREVIATIONS.extended(...)``), for example
with abbreviations harvested from its own reference list; ``split_sentences`` takes the set.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

# Personal titles: always followed by a name.
TITLES = frozenset({"dr.", "mr.", "mrs.", "ms.", "prof.", "st.", "sen.", "gen.", "hon."})

# Citation and agency abbreviations (NIST, legal and journal references).
CITATIONS = frozenset(
    {
        "natl.", "inst.", "stand.", "technol.", "spec.", "publ.", "seq.", "proc.", "conf.",
        "trans.", "intl.", "int.", "assoc.", "univ.", "dept.", "u.s.c.", "c.f.r.",
        "ed.", "eds.", "repr.", "suppl.",
    }
)  # fmt: skip

# Latin and comparison abbreviations, and the TERM-4 academic ones (EVAL-4 term_abbreviation_04:
# the splitter cut after "w.r.t."). The splitter reads the last token, so "op. cit." needs "op."
# and "cit."; "et seq." is covered by "seq." in CITATIONS.
LATIN = frozenset(
    {
        "e.g.", "i.e.", "cf.", "viz.", "vs.", "approx.", "resp.", "ca.", "ibid.",
        "w.r.t.", "s.t.", "w.l.o.g.", "op.", "cit.",
    }
)  # fmt: skip

# Document references: figures, equations, sections and theorem-like labels.
DOCUMENT_REFERENCES = frozenset(
    {
        "fig.", "figs.", "eq.", "eqs.", "sec.", "sect.", "secs.", "ref.", "refs.", "tab.",
        "app.", "thm.", "def.", "prop.", "lem.", "cor.", "ch.", "chap.", "alg.", "ex.",
    }
)  # fmt: skip

# Followed by a number: "No. 5", "Vol. 3", "pp. 12-19", "Rev. 2", "Art. 4".
BEFORE_NUMBER = frozenset({"no.", "nos.", "vol.", "vols.", "pp.", "p.", "art.", "par.", "rev."})

# Units and quantities, and company/name suffixes: may end a sentence.
MAY_END = frozenset(
    {
        "etc.", "inc.", "ltd.", "co.", "corp.", "jr.", "sr.", "al.", "i.i.d.", "u.s.",
        "min.", "max.", "est.", "avg.", "hr.", "hrs.", "sq.", "ft.", "lb.", "lbs.", "oz.",
    }
)  # fmt: skip


@dataclass(frozen=True)
class AbbreviationSet:
    """The three abbreviation behaviours the splitter consults."""

    non_terminal: frozenset[str] = field(default_factory=frozenset)
    before_number: frozenset[str] = field(default_factory=frozenset)
    may_end: frozenset[str] = field(default_factory=frozenset)

    def extended(
        self,
        *,
        non_terminal: Iterable[str] = (),
        before_number: Iterable[str] = (),
        may_end: Iterable[str] = (),
    ) -> AbbreviationSet:
        """A copy with extra entries (per-document extension); entries are lowercased."""
        return AbbreviationSet(
            self.non_terminal | {a.lower() for a in non_terminal},
            self.before_number | {a.lower() for a in before_number},
            self.may_end | {a.lower() for a in may_end},
        )


DEFAULT_ABBREVIATIONS = AbbreviationSet(
    non_terminal=TITLES | CITATIONS | LATIN | DOCUMENT_REFERENCES,
    before_number=BEFORE_NUMBER,
    may_end=MAY_END,
)
