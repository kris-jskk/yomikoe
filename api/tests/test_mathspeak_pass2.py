"""Reader pass 2 (MATH-1..3, gate b): number sign, identifiers, products, operator norms, and
text-font maths split from its neighbours (spec §3c rows dated 2026-10-17)."""

from __future__ import annotations

import re

import pytest

from yomikoe.ingestion.mathspeak import (
    char_map_errors,
    glyph_spans,
    join_spans,
    speak_segment,
)
from yomikoe.ingestion.mathspeak.markup import markup_segment


def said(raw: str) -> str:
    text, spans = markup_segment(raw, "equation")
    return speak_segment(text, spans)[0]


def prose(text: str) -> tuple[str, list[int], list]:  # type: ignore[type-arg]
    spans = join_spans(text, glyph_spans(text, []))
    out, cmap = speak_segment(text, spans)
    return out, cmap, spans


def words(s: str) -> str:
    return " ".join(re.sub(r"[^\w\s']", " ", s.lower()).split())


@pytest.mark.parametrize(
    ("raw", "spoken"),
    [
        ("x = µ + ( # ofSTDEV)(σ)", "x equals mu plus number of stdev times sigma"),
        ("# of x", "number of x"),
        ("STDEV", "stdev"),
        ("|||A|||_{H}", "the operator norm of a sub h"),
        ("(µP)(A)", "mu p of a"),
        ("(a + b)(c)", "a plus b times c"),
        ("s^{′⊤}", "s prime transpose"),
        ("E|R_{n}|", "e the absolute value of r sub n"),
        ("p(y | x)", "p of y given x"),
        (
            "sup_{f} |μ(f) − ν(f)|",
            "the supremum over f of the absolute value of mu of f minus nu of f",
        ),
        ("q : (x, d) ↦ y", "q from x, d maps to y"),
    ],
)
def test_math1_reader_pass2_wordings(raw: str, spoken: str) -> None:
    assert said(raw) == spoken


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "value = mean + (#ofSTDEVs)(standard deviation) here",
            "value equals mean plus number of stdevs times standard deviation here",
        ),
        ("for mu ∈P(X) we", "for mu in p of x we"),
        ("maps f : X → ℝ with", "maps f from x to r with"),
        ("for every t ≥1, it", "for every t is greater than or equal to 1 it"),
        ("The symbol x¯is the mean", "the symbol x bar is the mean"),
        ("Setting m := 0 and", "setting m is defined as 0 and"),
        ("the term ∆subopt is", "the term capital delta subopt is"),
    ],
)
def test_math2_text_font_maths_joined_and_glued(text: str, expected: str) -> None:
    out, cmap, spans = prose(text)
    assert words(out) == expected
    assert char_map_errors(text, out, cmap, spans) == []


def test_math2_prose_without_maths_is_untouched() -> None:
    text = "A plain sentence (with a note) and C++ code."
    out, _, spans = prose(text)
    assert spans == []
    assert "times" not in out
