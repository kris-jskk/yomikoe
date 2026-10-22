"""MATH-3 (spec §3c arrows): ⇀ (U+21C0), weak convergence, reads "converges weakly to".

Equation (2) of ``tables_04_markov_kernel.pdf``: "µ̂_t ⇀ π" was spoken "mu hat sub t pi", the
arrow lost (m5-p5h, supervisor decision 2026-10-21, open to the user).
"""

from __future__ import annotations

from yomikoe.ingestion.mathspeak import speak_span, symbols
from yomikoe.ingestion.mathspeak.markup import markup_segment


def _eq(raw: str) -> str:
    text, (span,) = markup_segment(raw, "equation")
    spoken, _ = speak_span(span, text)
    return spoken


def test_math3_weak_convergence_arrow_has_a_name() -> None:
    assert symbols.name_of("⇀") == "converges weakly to"


def test_math3_weak_convergence_arrow_is_spoken() -> None:
    assert _eq("x ⇀ π") == "x converges weakly to pi"


def test_math3_less_or_similar_relations_have_names() -> None:
    # m5-p5i: tables_04 equation (6) dropped "≲"
    assert symbols.name_of("≲") == "is less than or similar to"
    assert symbols.name_of("≳") == "is greater than or similar to"


def test_math3_less_or_similar_relation_is_spoken() -> None:
    assert _eq("a ≲ b") == "a is less than or similar to b"
    assert _eq("a ≳ b") == "a is greater than or similar to b"
