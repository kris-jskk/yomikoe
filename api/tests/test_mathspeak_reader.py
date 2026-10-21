"""MATH-1, MATH-2, MATH-4, D36: §3c wordings, fallback, references, speak_segment and char_map."""

from __future__ import annotations

from dataclasses import replace

import pytest

from yomikoe.ingestion.mathspeak import (
    apply_mathspeak,
    char_map_errors,
    speak_segment,
    speak_span,
)
from yomikoe.ingestion.mathspeak.markup import markup_segment
from yomikoe.ingestion.mathspeak.reader import fallback, speak
from yomikoe.ingestion.mathspeak.references import rewrite_references
from yomikoe.ingestion.mathspeak.structure import MathSpan, parse
from yomikoe.ingestion.models import LogicalBlock, Segment
from yomikoe.ingestion.profile import PROSE_DEFAULT

MATH = replace(PROSE_DEFAULT, override="math")


def said(raw: str, profile=None) -> str:  # type: ignore[no-untyped-def]
    text, spans = markup_segment(raw, "equation")
    return speak_segment(text, spans, profile)[0]


@pytest.mark.parametrize(
    ("raw", "spoken"),
    [
        ("x_{ij}^{2}", "x sub i j, squared"),
        ("x^{(j)}", "x sup j"),
        ("π^{sel}", "pi sup sel"),
        ("x_{emp}", "x sub emp"),
        ("x^{T} y^{*}", "x transpose y star"),
        ("x^{−1}", "x to the minus 1"),
        ("x^{1/2}", "x to the 1 half"),
        ("a\nb", "a over b"),
        ("a + b\nc", "the fraction a plus b over c, end fraction"),
        ("∑_{i>r} a_{i}", "the sum over i greater than r of a sub i"),
        ("∫ f", "the integral of f"),
        ("lim_{x→a} f(x)", "the limit as x approaches a of f of x"),
        ("min(a, b)", "the minimum of a and b"),
        ("max_{i} x_{i}", "the maximum over i of x sub i"),
        ("√(x + 1)", "the square root of x plus 1"),
        ("2(k − 1)", "2 times k minus 1"),
        ("E[X]²", "e of x, squared"),
        ("sin(x) + cos θ", "sine of x plus cosine theta"),
        ("det(A) = tr(B)", "the determinant of a equals the trace of b"),
        ("p(y | x)", "p of y given x"),
        ("{x : x > 0}", "the set of x such that x is greater than 0"),
        ("⟨f, g⟩", "the inner product of f and g"),
        (
            "[0, 1) ∪ (2, 3]",
            "the interval from 0 to 1, exclusive union the interval from 2, exclusive, to 3",
        ),
        ("x ∈ (0, 1)", "x in the open interval from 0 to 1"),
        ("[a b\nc d]", "the matrix with rows: a, b; c, d"),
        ("x̂ + ȳ", "x hat plus y bar"),
        ("f′(x)", "f prime of x"),
        ("n!", "n factorial"),
        ("y = ax + b          (3)", "equation 3: y equals a x plus b"),
    ],
)
def test_math1_reader_wordings(raw: str, spoken: str) -> None:
    assert said(raw) == spoken


def test_math1_prose_profile_reads_brackets_as_a_list() -> None:
    assert said("x ∈ [0, 1]", PROSE_DEFAULT) == "x in 0, 1"
    assert said("x ∈ [0, 1]", MATH) == "x in the interval from 0 to 1"


def test_math1_fallback_names_every_symbol_and_is_never_empty() -> None:
    text, (span,) = markup_segment("a ☃ ≤ b          (4)", "equation")
    assert parse(span, text) is None
    assert fallback(span, text) == "equation 4 a is less than or equal to b"
    # the segment reads the partial parse: the prefix, the structured parts, ☃ has no name
    assert speak_segment(text, [span])[0] == "equation 4: a is less than or equal to b"
    assert fallback(MathSpan(0, 1, True, []), "☃") == "equation"
    node = parse(markup_segment("x + 1", "equation")[1][0])
    assert node is not None and speak(node) == "x plus 1"


def test_math4_references_with_offsets() -> None:
    text = "By Eq. (3) and Eqs. 3–5, also Eqs. (3) and (4), Equation 7."
    edits = rewrite_references(text)
    spoken = [e[2] for e in edits]
    assert spoken == ["equation 3", "equations 3 to 5", "equations 3 and 4", "equation 7"]
    assert text[edits[0][0] : edits[0][1]] == "Eq. (3)"
    assert rewrite_references("Theorem 2.1 Every set.") == [(0, 11, "Theorem 2.1,")]
    assert rewrite_references("Proof By induction.") == [(0, 5, "Proof,")]
    assert rewrite_references("Theorem 2.1 states that.") == []
    assert rewrite_references("We use the Definition Above.") == []


MIXED = [
    "Let $x_{i}$ be the i-th sample and $σ²$ its variance, see Eq. (2).",
    "For $k ≥ 1$ the bound $|a_{k}| ≤ 2^{−k}$ holds over 5 km of H2O [12].",
    "Theorem 3 If $f(x) = ∑_{n=0}^{∞} a_{n} x^{n}$ then $f ∈ [0, 1]$.",
]


@pytest.mark.parametrize("raw", MIXED)
def test_math2_char_map_rule_on_mixed_segments(raw: str) -> None:
    text, spans = markup_segment(raw, "body")
    assert len(spans) >= 1
    out, cmap = speak_segment(text, spans, MATH)
    assert char_map_errors(text, out, cmap, spans) == []
    assert out.isascii()


def test_math2_mixed_segment_text() -> None:
    text, spans = markup_segment(MIXED[1], "body")
    out, _ = speak_segment(text, spans, MATH)
    assert out == (
        "For k is greater than or equal to 1 the bound the absolute value of a sub k is less "
        "than or equal to 2 to the minus k holds over 5 kilometers of h 2 o."
    )


def test_math2_apply_mathspeak_clips_spans_to_segments_and_rereads_math_json() -> None:
    text, spans = markup_segment("We start. Then $x_{i}$ is fixed.", "body")
    block = LogicalBlock(id=0, page=0, type="body", text=text, source=[(0, 0)])
    block.math_spans = spans  # type: ignore[attr-defined]
    cut = text.index("Then")
    segs = [
        Segment(i, 1, 0, i, None, text[a:b], text[a:b], a, b, list(range(b - a)))
        for i, (a, b) in enumerate(((0, cut - 1), (cut, len(text))))
    ]
    apply_mathspeak(segs, [block], [], None)
    assert segs[0].normalized_text == "We start." and getattr(segs[0], "math_json", None) is None
    assert segs[1].normalized_text == "Then x sub i is fixed."
    entries = segs[1].math_json  # type: ignore[attr-defined]
    assert entries and entries[0]["tree"] is not None and entries[0]["start"] == 5
    again = speak_segment(segs[1].text, entries, MATH)
    assert again == (segs[1].normalized_text, segs[1].char_map)
    assert speak_span(entries[0], segs[1].text)[0] == "x sub i"
