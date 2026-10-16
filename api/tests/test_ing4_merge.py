"""Stage 4, merge lines and cross-page blocks (ING-5)."""

import pytest

from hearnarro.ingestion.merge import merge_blocks, merge_lines
from tests.conftest import make_block


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
    assert [b.text for b in merge_blocks([host, frag])] == ["and E[P", "i D(p, q)] = O(1)."]
