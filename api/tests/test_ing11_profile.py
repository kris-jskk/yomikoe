"""ING-11 document profile (D40): thresholds on synthetic documents, citation style, JSON round
trip, ``PROSE_DEFAULT`` for NULL, and the bracket rule per class through ``normalize``."""

from __future__ import annotations

from hearnarro.ingestion.models import LogicalBlock, Page
from hearnarro.ingestion.normalize import normalize
from hearnarro.ingestion.profile import (
    PROSE_DEFAULT,
    DocumentProfile,
    citation_style,
    classify,
    compute_profile,
)

PROSE = (
    "The committee met twice and agreed on the plan, which the staff will carry out over "
    "the coming year with the support of the regional offices [12]. "
) * 6


def _pages(n: int) -> list[Page]:
    return [Page(number=i, width=612, height=792, blocks=[]) for i in range(n)]


def _doc(spec: list[tuple[str, str]]) -> list[LogicalBlock]:
    return [
        LogicalBlock(
            id=i,
            page=0,
            type=t,  # type: ignore[arg-type]
            text="Equation." if t == "equation" else text,
            source=[(0, i)],
            raw_text=text if t == "equation" else None,
        )
        for i, (t, text) in enumerate(spec)
    ]


def test_ing11_prose_document_is_prose() -> None:
    p = compute_profile(_pages(2), _doc([("heading", "Introduction"), ("body", PROSE)] * 2))
    assert p.cls == "prose" and p.effective == "prose"
    assert p.math_share == 0.0 and p.display_per_page == 0.0
    assert p.citation_style == "numeric"  # 12 bracket clusters >= 3


def test_ing11_one_display_equation_over_two_pages_is_mixed() -> None:
    blocks = _doc(
        [
            ("body", PROSE),
            ("equation", "y = a x + b + e, with e = y − ŷ minimised over a and b in ℝ"),
            ("body", PROSE),
        ]
    )
    p = compute_profile(_pages(2), blocks)
    assert p.display_per_page == 0.5
    assert 0.0 < p.math_share < 0.15
    assert p.cls == "mixed"


def test_ing11_two_displays_per_page_is_math_and_rows_of_one_display_count_once() -> None:
    eq = [("equation", "f(x) = ∑ a_i x^i"), ("equation", "g(x) = ∫ f(t) dt")]  # one display
    blocks = _doc([("body", PROSE), *eq, ("body", "where"), *eq, ("body", PROSE)])
    p = compute_profile(_pages(1), blocks)
    assert p.display_per_page == 2.0  # two runs of equation rows, not four rows
    assert p.cls == "math"


def test_ing11_dense_inline_maths_is_math_without_equation_blocks() -> None:
    body = "Let σ = √(∑(x − μ)² / N) where μ is the mean and N ≥ 1 is the count. " * 8
    p = compute_profile(_pages(1), _doc([("body", body)]))
    assert p.display_per_page == 0.0
    assert p.inline_token_share >= 0.04
    assert p.cls == "math"


def test_ing11_thresholds_d40_as_tuned() -> None:
    assert classify(0.15, 0.0) == "math"
    assert classify(0.0, 2.0) == "math"
    assert classify(0.0, 0.0, inline_token_share=0.04) == "math"
    assert classify(0.009, 0.5) == "prose"
    assert classify(0.0, 0.0, code_share=0.10) == "mixed"  # a code listing is not prose
    assert classify(0.01, 0.0) == "mixed"
    assert classify(0.0, 1.0) == "mixed"


def test_ing11_citation_style_author_year_and_none() -> None:
    texts = ["As shown (Smith et al., 2020) and (Jones and Lee, 2019) and (Kim, 2021a)."]
    assert citation_style(texts) == "author_year"
    assert citation_style(["One [1] and two [2]."]) == "none"  # fewer than 3


def test_ing11_json_round_trip_and_prose_default_for_null() -> None:
    p = compute_profile(_pages(1), _doc([("body", PROSE)])).with_override("math", "skip")
    back = DocumentProfile.from_json(p.to_json())
    assert back == p and back.effective == "math" and back.cls == "prose"
    assert DocumentProfile.from_json(None) is PROSE_DEFAULT
    assert DocumentProfile.from_json("") is PROSE_DEFAULT
    assert PROSE_DEFAULT.effective == "prose"


TEXT = "Let x lie in [1, 2] as before [12]."
SPAN = (TEXT.index("[1, 2]"), TEXT.index("[1, 2]") + len("[1, 2]"))  # a maths span (MATH-2)


def _with(cls: str) -> DocumentProfile:
    return PROSE_DEFAULT.with_override(cls)  # type: ignore[arg-type]


def test_ing11_bracket_rule_prose_drops_both() -> None:
    assert normalize(TEXT)[0] == "Let x lie in as before."  # today's rule, unchanged default
    assert normalize(TEXT, profile=_with("prose"), math_spans=[SPAN])[0] == normalize(TEXT)[0]
    # ING-6: a group starting with 0 is never a citation (main 5b09a5f)
    assert normalize("Let x lie in [0, 1] as before [12].")[0] == "Let x lie in [0, 1] as before."


def test_ing11_bracket_rule_math_keeps_maths_span_drops_citation() -> None:
    out, cmap = normalize(TEXT, profile=_with("math"), math_spans=[SPAN])
    assert out == "Let x lie in [1, 2] as before."
    assert len(cmap) == len(out)
    i = out.index("[1, 2]")
    assert cmap[i : i + 6] == list(range(SPAN[0], SPAN[1]))


def test_ing11_bracket_rule_mixed_per_span() -> None:
    assert (
        normalize(TEXT, profile=_with("mixed"), math_spans=[SPAN])[0]
        == "Let x lie in [1, 2] as before."
    )
    # no maths span: a citation-shaped group is dropped even in a math document
    assert normalize(TEXT, profile=_with("math"))[0] == "Let x lie in as before."


def test_ing11_ingest_result_carries_profile() -> None:
    from hearnarro.evals.suites import _fixtures

    result = _fixtures.ingest_result("report_01_zero_trust")
    assert result.profile.cls == "prose"


def test_ing11_code_words_count_in_the_token_share() -> None:
    """A short docs page: four maths tokens in 80 prose words is 5 % on prose alone, but the
    listing's words are read mass too, so the share falls under 4 % (formula_08, m5-p3f)."""
    words = ("word " * 76).strip()
    prose = f"{words} lim𝑥→0 sin(𝑥)/𝑥 𝑙𝑜𝑔(𝑥) 𝑥."
    blocks = _doc([("body", prose)])
    assert compute_profile(_pages(1), blocks).inline_token_share >= 0.04
    code = LogicalBlock(
        id=1,
        page=0,
        type="code",
        text="Code listing, 6 lines.",
        source=[(0, 1)],
        raw_text="from sympy import integrate, symbols, limit, sin, log\n" * 6,
    )
    profile = compute_profile(_pages(1), [*blocks, code])
    assert profile.inline_token_share < 0.04
    assert profile.cls == "mixed"


def test_ing11_content_spans_do_not_add_inline_mass() -> None:
    """A content span (no runs, ``merge.content_spans``) widens over operand words; only spans
    with geometry (maths-font runs) count, the token estimate is the floor."""
    from hearnarro.ingestion.models import MathSpan

    text = PROSE + "so value = mean plus deviation here"
    start = text.index("value")
    block = LogicalBlock(id=0, page=0, type="body", text=text, source=[(0, 0)])
    base = compute_profile(_pages(1), [block]).math_share
    block.math_spans = [MathSpan(start, start + 30, False, [])]
    assert compute_profile(_pages(1), [block]).math_share == base
