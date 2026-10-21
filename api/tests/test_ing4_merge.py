"""Stage 4, merge lines and cross-page blocks (ING-5)."""

import pytest

from tests.conftest import make_block
from yomikoe.ingestion.merge import merge_blocks, merge_lines
from yomikoe.ingestion.models import Block
from yomikoe.ingestion.order import attach_inline


@pytest.mark.parametrize(
    ("lines", "expected"),
    [
        (["The quick brown", "fox jumps"], "The quick brown fox jumps"),
        (["an exam-", "ple of this"], "an example of this"),
        (["a well-", "Known result"], "a well- Known result"),
        (["re-", ""], "re-"),
        (["  spaced   out ", "\tline  "], "spaced out line"),
        (["single"], "single"),
        ([], ""),
    ],
)
def test_ing5_merge_lines(lines: list[str], expected: str) -> None:
    assert merge_lines(lines) == expected


@pytest.mark.parametrize("hyphen", ["\u2010", "\u2011"], ids=["U+2010", "U+2011"])
def test_ing5_merge_lines_unicode_hyphen_lowercase_dehyphenates(hyphen: str) -> None:
    assert merge_lines([f"a wide-ranging dis{hyphen}", "cussion"]) == "a wide-ranging discussion"


@pytest.mark.parametrize("hyphen", ["\u2010", "\u2011"], ids=["U+2010", "U+2011"])
def test_ing5_merge_lines_unicode_hyphen_uppercase_keeps_hyphen(hyphen: str) -> None:
    assert merge_lines([f"a well{hyphen}", "Known result"]) == f"a well{hyphen} Known result"


@pytest.mark.parametrize(
    ("lines", "expected"),
    [
        (["tak\u00ad", "ing familiar"], "taking familiar"),
        (["Inter\u00ad", "Net"], "InterNet"),
    ],
)
def test_ing5_merge_lines_soft_hyphen_always_removed(lines: list[str], expected: str) -> None:
    assert merge_lines(lines) == expected


def test_ing5_merge_blocks_dehyphenates_unicode_hyphen_across_page_break() -> None:
    blocks = [
        make_block(0, 0, ["a well-known dis\u2010"], y0=600),
        make_block(1, 0, ["cussion of this."], y0=50),
    ]
    assert [lb.text for lb in merge_blocks(blocks)] == ["a well-known discussion of this."]


def test_ing5_merge_blocks_soft_hyphen_at_line_end_always_removed() -> None:
    blocks = [
        make_block(0, 0, ["Inter\u00ad", "Net of tak\u00ad"], y0=600),
        make_block(1, 0, ["ing things\u00ad"], y0=50),
        make_block(1, 1, ["A new soft\u00ad", ""], y0=300, type="heading"),
    ]
    assert [lb.text for lb in merge_blocks(blocks)] == [
        "InterNet of taking things",
        "A new soft",
    ]


def test_ing5_merge_blocks_one_per_block_with_merged_lines() -> None:
    blocks = [
        make_block(0, 0, ["Introduction"], type="heading"),
        make_block(0, 1, ["The quick brown fox jum-", "ped over the dog."], y0=100),
    ]
    logical = merge_blocks(blocks)
    assert [lb.id for lb in logical] == [0, 1]
    assert [lb.text for lb in logical] == [
        "Introduction",
        "The quick brown fox jumped over the dog.",
    ]
    assert [lb.type for lb in logical] == ["heading", "body"]
    assert [lb.source for lb in logical] == [[(0, 0)], [(0, 1)]]
    assert [lb.page for lb in logical] == [0, 0]


def test_ing5_merge_blocks_joins_sentence_across_page_break_past_footer() -> None:
    blocks = [
        make_block(0, 0, ["First paragraph ends here."], y0=100),
        make_block(0, 1, ["The results show that the"], y0=600),
        make_block(0, 2, ["Page 1"], y0=760, type="footer"),
        make_block(1, 0, ["method works well."], y0=100),
        make_block(1, 1, ["Another paragraph."], y0=200),
    ]
    logical = merge_blocks(blocks)
    assert [lb.id for lb in logical] == list(range(len(logical)))
    joined = [lb for lb in logical if lb.source == [(0, 1), (1, 0)]]
    assert len(joined) == 1
    assert joined[0].text == "The results show that the method works well."
    assert joined[0].page == 0
    assert joined[0].type == "body"
    assert not any(lb.source == [(0, 1)] for lb in logical)
    assert not any(lb.source == [(1, 0)] for lb in logical)
    texts = [lb.text for lb in logical]
    assert texts.index("First paragraph ends here.") < texts.index(joined[0].text)
    assert texts.index(joined[0].text) < texts.index("Another paragraph.")


def test_ing5_merge_blocks_dehyphenates_across_page_break() -> None:
    blocks = [
        make_block(0, 0, ["a well-known exam-"], y0=600),
        make_block(1, 0, ["ple of this."], y0=100),
    ]
    logical = merge_blocks(blocks)
    assert [lb.text for lb in logical] == ["a well-known example of this."]
    assert logical[0].source == [(0, 0), (1, 0)]


def test_ing5_merge_blocks_lowercase_continuation_joins_even_after_period() -> None:
    blocks = [
        make_block(0, 0, ["It ended with an abbrev. e.g."], y0=600),
        make_block(1, 0, ["and then continued."], y0=100),
    ]
    logical = merge_blocks(blocks)
    assert len(logical) == 1
    assert logical[0].text == "It ended with an abbrev. e.g. and then continued."


def test_ing5_merge_blocks_keeps_separate_paragraphs_across_page_break() -> None:
    blocks = [
        make_block(0, 0, ["The paragraph ends here."], y0=600),
        make_block(1, 0, ["A new paragraph starts."], y0=100),
    ]
    logical = merge_blocks(blocks)
    assert [lb.text for lb in logical] == ["The paragraph ends here.", "A new paragraph starts."]
    assert [lb.id for lb in logical] == [0, 1]
    assert [lb.page for lb in logical] == [0, 1]


def test_ing5_merge_blocks_does_not_join_non_body() -> None:
    blocks = [
        make_block(0, 0, ["Section heading without period"], y0=600, type="heading"),
        make_block(1, 0, ["continues in lowercase."], y0=100),
    ]
    logical = merge_blocks(blocks)
    assert len(logical) == 2


def test_ing5_merge_blocks_joins_sentence_across_column_break() -> None:
    blocks = [
        make_block(0, 0, ["The left column ends with a sentence that"], x0=50, width=240, y0=700),
        make_block(0, 1, ["continues at the top of the right column."], x0=322, width=240, y0=80),
    ]
    logical = merge_blocks(blocks)
    assert [lb.text for lb in logical] == [
        "The left column ends with a sentence that continues at the top of the right column."
    ]


def test_ing5_merge_blocks_does_not_join_within_a_column() -> None:
    blocks = [
        make_block(0, 0, ["A paragraph without a period"], y0=100),
        make_block(0, 1, ["lowercase block further down the same column."], y0=200),
    ]
    assert len(merge_blocks(blocks)) == 2


def test_ing5_merge_blocks_moves_only_first_sentence_past_a_float() -> None:
    blocks = [
        make_block(0, 0, ["Results show that the"], x0=50, width=240, y0=700),
        make_block(0, 1, ["Figure 1: A caption."], x0=322, width=240, y0=80, type="caption"),
        make_block(0, 2, ["tiny"], x0=322, width=40, y0=150, size=5),  # figure label
        make_block(0, 3, ["method works. A new sentence follows."], x0=322, width=240, y0=200),
    ]
    texts = [lb.text for lb in merge_blocks(blocks)]
    assert texts == [
        "Results show that the method works.",
        "Figure 1: A caption.",
        "tiny",
        "A new sentence follows.",
    ]


def test_ing5_merge_blocks_drops_email_only_and_boilerplate_lines() -> None:
    blocks = [make_block(1, 0, ["Jane Doe", "jane@uni.edu", "This publication is available free"])]
    assert [lb.text for lb in merge_blocks(blocks)] == [
        "Jane Doe This publication is available free"
    ]
    blocks = [make_block(1, 0, ["Jane Doe", "This publication is available free of charge from:"])]
    assert [lb.text for lb in merge_blocks(blocks)] == ["Jane Doe"]


def test_ing5_merge_blocks_strips_emails_in_page0_author_block_only() -> None:
    blocks = [
        make_block(0, 0, ["AI Singapore, Singapore a.b,c@aisingapore.org"], y0=100),
        make_block(0, 1, ["Abstract"], y0=200, type="heading"),
        make_block(0, 2, ["Write to us at help@example.org for details."], y0=300),
    ]
    texts = [lb.text for lb in merge_blocks(blocks)]
    assert texts[0] == "AI Singapore, Singapore"
    assert texts[2] == "Write to us at help@example.org for details."


def test_ing5_merge_blocks_joins_inline_fragment_into_previous_block() -> None:
    host = make_block(0, 0, ["and E[P"], x0=72, width=100, y0=100)
    frag = make_block(0, 1, ["i D(p, q)] = O(1)."], x0=172, width=80, y0=100, type="equation")
    frag.inline = True
    nxt = make_block(0, 2, ["Next sentence."], x0=72, width=200, y0=113)
    out = merge_blocks([host, frag, nxt])
    assert [b.text for b in out] == ["and E[P i D(p, q)] = O(1).", "Next sentence."]
    assert out[0].source == [(0, 0), (0, 1)] and out[0].type == "body"


def test_ing5_merge_blocks_keeps_fragment_not_marked_inline() -> None:
    host = make_block(0, 0, ["and E[P"], x0=72, width=100, y0=100)
    frag = make_block(0, 1, ["i D(p, q)] = O(1)."], x0=172, width=80, y0=100, type="equation")
    # MATH-1: an equation block keeps its raw text with one display span (no ING-7 cue).
    out = merge_blocks([host, frag])
    assert [b.text for b in out] == ["and E[P", "i D(p, q)] = O(1)."]
    assert [(s.start, s.end, s.display) for s in out[1].math_spans] == [(0, 18, True)]


# --- D12 rule 2: inline maths joins its host sentence whatever the extraction order --------


def _inline_case() -> tuple[Block, Block, Block]:
    host = make_block(
        0, 0, ["the training loss is bounded above by the norm of"], x0=72, width=200, y0=100
    )
    frag = make_block(0, 1, ["r )∥2"], x0=274, width=24, y0=100, type="equation")
    nxt = make_block(0, 2, ["Next sentence of the paragraph."], x0=72, width=300, y0=113)
    return host, frag, nxt


def test_ing5_d12_inline_math_in_order_chain_joins_host() -> None:
    host, frag, nxt = _inline_case()
    out = merge_blocks(attach_inline([host, frag, nxt]))
    assert [b.text for b in out] == [
        "the training loss is bounded above by the norm of r )∥2",
        "Next sentence of the paragraph.",
    ]
    assert out[0].source == [(0, 0), (0, 1)]


def test_ing5_d12_inline_math_out_of_order_chain_joins_host() -> None:
    host, frag, nxt = _inline_case()
    out = merge_blocks(attach_inline([host, nxt, frag]))
    assert [b.text for b in out] == [
        "the training loss is bounded above by the norm of r )∥2",
        "Next sentence of the paragraph.",
    ]


def test_ing5_d12_display_equation_stays_separate() -> None:
    host = make_block(0, 0, ["We minimise the following objective:"], x0=72, width=200, y0=100)
    eq = make_block(0, 1, ["L = ∑ ∥x − y∥2"], x0=200, width=120, y0=130, type="equation")
    nxt = make_block(0, 2, ["where x is the input."], x0=72, width=300, y0=160)
    out = merge_blocks(attach_inline([host, eq, nxt]))
    assert [(b.type, b.text) for b in out] == [
        ("body", "We minimise the following objective:"),
        ("equation", "L = ∑ ∥x − y∥2"),  # MATH-1: raw text kept, read by mathspeak
        ("body", "where x is the input."),
    ]
    assert [s.display for s in out[1].math_spans] == [True]
    assert not eq.inline


# --- found on a user book (The Almanack of Naval Ravikant, 2026-10-16): an untagged
# justified book whose lines start 0.5-2 pt apart, so stage 1 opens a block mid-paragraph ---


def _para(index: int, text: str, y0: float, type: str = "body") -> Block:
    return make_block(0, index, [text], y0=y0, type=type)  # type: ignore[arg-type]


@pytest.fixture
def joins_on(monkeypatch: pytest.MonkeyPatch) -> None:
    """Short synthetic documents: lower the document-level gate (PARA_JOIN_MIN_COUNT)."""
    monkeypatch.setattr("yomikoe.ingestion.merge.PARA_JOIN_MIN_COUNT", 1)


@pytest.mark.usefixtures("joins_on")
def test_ing5_same_page_fragments_join_when_a_is_unpunctuated_and_b_lowercase() -> None:
    blocks = [
        _para(0, "They started out reading a set of weakly true things,", 100),
        _para(1, "and those formed the axioms of their worldview.", 115),
        _para(2, "When you are reading a book and you are confused, that con-", 150),
        _para(3, "fusion is similar to the pain in the gym.", 165),
        _para(4, "The best way to have a foundation", 200),
        _para(5, "(you may not love this answer) is science.", 215),
        _para(6, "The best way to have a high-quality foundation (you may not", 250),
        _para(7, "love this answer), but the trick is science.", 265),
    ]
    assert [lb.text for lb in merge_blocks(blocks)] == [
        (
            "They started out reading a set of weakly true things, "
            "and those formed the axioms of their worldview."
        ),
        (
            "When you are reading a book and you are confused, that confusion is similar to "
            "the pain in the gym."
        ),
        "The best way to have a foundation (you may not love this answer) is science.",
        (
            "The best way to have a high-quality foundation (you may not love this answer), "
            "but the trick is science."
        ),
    ]


@pytest.mark.usefixtures("joins_on")
def test_ing5_same_page_no_join_after_terminal_punct_uppercase_or_heading() -> None:
    blocks = [
        _para(0, "Your foundation is critical.", 100),
        _para(1, "and this starts lowercase after a full stop.", 115),
        _para(2, "This line has no full stop", 150),
        _para(3, "Then an uppercase start is a new paragraph.", 165),
        _para(4, "A section ends without punctuation", 200),
        _para(5, "Reading", 215, type="heading"),
        _para(6, "lowercase after a heading stays apart.", 230),
    ]
    assert len(merge_blocks(blocks)) == 7


def test_ing5_same_page_joins_only_when_systematic_in_the_document() -> None:
    """Fewer than PARA_JOIN_MIN_COUNT candidate pairs (or under PARA_JOIN_MIN_SHARE of the body
    blocks): stage 1's splits are kept, as the golden ground truth expects."""
    few = [_para(0, "a sentence without an end", 100), _para(1, "continues here.", 115)]
    assert len(merge_blocks(few)) == 2
    many: list[Block] = []
    for i in range(12):
        many += [
            _para(2 * i, f"paragraph {i} runs on and on", 100 + 40 * i),
            _para(2 * i + 1, "and ends on the next line.", 115 + 40 * i),
        ]
    assert len(merge_blocks(many)) == 12


ARROW_ITEMS = [
    "→ Questions nearly everything",
    "→ Can think from first principles",
    "→ Tests things well",
    "→ Is good at not fooling himself",
    "→ Changes his mind regularly",
    "→ Laughs a lot",
    "→ Thinks holistically",
    "→ Thinks long-term",
    "→ And…doesn’t take himself too goddamn seriously.",
]


def test_ing5_list_block_split_into_one_logical_block_per_item() -> None:
    blocks = [
        make_block(0, 0, ["I take Naval seriously because he:"], y0=60),
        make_block(0, 1, ARROW_ITEMS, y0=100, type="list"),
        make_block(0, 2, ["That is why."], y0=300),
    ]
    logical = merge_blocks(blocks)
    assert [lb.text for lb in logical] == [
        "I take Naval seriously because he:",
        *ARROW_ITEMS,
        "That is why.",
    ]
    assert [lb.id for lb in logical] == list(range(11))
    assert [lb.type for lb in logical[1:10]] == ["list"] * 9
    assert all(lb.source == [(0, 1)] for lb in logical[1:10])


def test_ing5_list_items_split_across_page_break_are_not_joined() -> None:
    blocks = [
        make_block(0, 0, ARROW_ITEMS[:3], y0=600, type="list"),
        make_block(1, 0, ARROW_ITEMS[3:], y0=60, type="list"),
    ]
    assert [lb.text for lb in merge_blocks(blocks)] == ARROW_ITEMS


def test_ing5_list_item_continuation_lines_join_their_item() -> None:
    lines = [
        "→ The transcripts have been edited for clarity and brevity",
        "(multiple times).",
        "→ 2003 - Founder of Vast.com, a classified ad mar-",
        "ketplace",
        "→ Uses cloud",
        "-based storage",
    ]
    assert [lb.text for lb in merge_blocks([make_block(0, 0, lines, type="list")])] == [
        "→ The transcripts have been edited for clarity and brevity (multiple times).",
        "→ 2003 - Founder of Vast.com, a classified ad marketplace",
        "→ Uses cloud -based storage",
    ]


def test_ing5_inline_glyph_items_split() -> None:
    blocks = [make_block(0, 0, ["→ Education → The Story of AngelList"], type="list")]
    assert [lb.text for lb in merge_blocks(blocks)] == ["→ Education", "→ The Story of AngelList"]


def test_ing5_dash_star_and_numbered_items_split() -> None:
    lines = [
        "- Dash item",
        "* Star item",
        "1. First step",
        "2) Second step",
        "(3) Third",
        "a. Four",
    ]
    blocks = [make_block(0, 0, lines, type="list")]
    assert [lb.text for lb in merge_blocks(blocks)] == lines


def test_ing5_glyph_alone_on_its_line_joins_the_next_line() -> None:
    blocks = [make_block(0, 0, ["•", "Item text", "•", "Other item"], type="list")]
    assert [lb.text for lb in merge_blocks(blocks)] == ["• Item text", "• Other item"]


def test_ing5_dot_leader_ellipsis_in_a_list_item_is_not_split() -> None:
    line = "2. With eigenvalues ordered as λ1(C) ≥· · · ≥λd(C), a top-r basis."
    assert [lb.text for lb in merge_blocks([make_block(0, 0, [line], type="list")])] == [line]
