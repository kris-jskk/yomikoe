"""Academic abbreviations spoken by expansion (TERM-4, spec §4c).

This one table is what PRD TERM-4 calls configurable: ``normalize`` (stage 5) replaces each key,
matched as a whole token and case-insensitively, with its wording. It is separate from
``abbreviations``, which only stops sentence splits after these forms and is unchanged.
"""

from __future__ import annotations

EXPANSIONS: dict[str, str] = {
    "i.e.": "that is",
    "e.g.": "for example",
    "cf.": "compare",
    "w.r.t.": "with respect to",
    "resp.": "respectively",
    "s.t.": "such that",
    "iff": "if and only if",
    "w.l.o.g.": "without loss of generality",
    "viz.": "namely",
    "et seq.": "and following",
    "ibid.": "in the same place",
    "op. cit.": "in the work cited",
}
