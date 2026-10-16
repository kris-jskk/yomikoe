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
