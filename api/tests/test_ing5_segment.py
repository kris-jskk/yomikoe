"""Stage 5, sentence segmentation with offsets (D4, ING-5)."""

import itertools

import pytest

from hearnarro.ingestion.abbreviations import DEFAULT_ABBREVIATIONS
from hearnarro.ingestion.models import LogicalBlock
from hearnarro.ingestion.normalize import normalize
from hearnarro.ingestion.segment import split_sentences

TEXT = (
    "Dr. Smith et al. found 3.2% growth in the sample. "
    "See Fig. 2 for details. The effect held across all groups."
)


def _block(text: str = TEXT, id: int = 7) -> LogicalBlock:
    return LogicalBlock(id=id, page=0, type="body", text=text, source=[(0, 0)])


def test_ing5_split_sentences_three_sentences_with_abbreviations() -> None:
    segments = split_sentences(_block(), document_id=3, order_start=10, id_start=100)
    assert [s.text for s in segments] == [
        "Dr. Smith et al. found 3.2% growth in the sample.",
        "See Fig. 2 for details.",
        "The effect held across all groups.",
    ]


def test_ing5_split_sentences_offsets_round_trip() -> None:
    block = _block()
    for s in split_sentences(block, document_id=3, order_start=10, id_start=100):
        assert block.text[s.char_start : s.char_end] == s.text
        assert s.text == s.text.strip()
        assert s.text


def test_ing5_split_sentences_offsets_round_trip_with_messy_whitespace() -> None:
    block = _block("  First one here.   Second one follows.\nThird on a new line.  ")
    segments = split_sentences(block, document_id=0, order_start=0, id_start=0)
    assert segments
    for s in segments:
        assert block.text[s.char_start : s.char_end] == s.text
        assert s.text == s.text.strip()
    assert [s.char_start for s in segments] == sorted(s.char_start for s in segments)


def test_ing5_split_sentences_ids_orders_and_fields() -> None:
    segments = split_sentences(_block(id=7), document_id=3, order_start=10, id_start=100)
    assert [s.order for s in segments] == [10, 11, 12]
    assert [s.id for s in segments] == [100, 101, 102]
    for s in segments:
        assert s.block_id == 7
        assert s.document_id == 3
        assert s.section_id is None
        assert (s.normalized_text, s.char_map) == normalize(s.text)
        assert len(s.char_map) == len(s.normalized_text)


def test_ing5_split_sentences_empty_block() -> None:
    assert split_sentences(_block("   "), document_id=0, order_start=0, id_start=0) == []


# --- ING-5 boundary rules: abbreviations, initials, section numbers, closers (M2) -------------


def _texts(text: str) -> list[str]:
    return [s.text for s in split_sentences(_block(text), document_id=0, order_start=0, id_start=0)]


CASES: dict[str, tuple[str, list[str]]] = {
    "citation_abbreviations_mid_sentence": (
        (
            "This document is Natl. Inst. Stand. Technol. Spec. Publ. 800-207, 59 pages "
            "(August 2020). It is free."
        ),
        [
            (
                "This document is Natl. Inst. Stand. Technol. Spec. Publ. 800-207, 59 pages "
                "(August 2020)."
            ),
            "It is free.",
        ],
    ),
    "et_seq_then_comma": (
        "FISMA, 44 U.S.C. § 3551 et seq., Public Law (P.L.) 113-283. NIST is responsible.",
        [
            "FISMA, 44 U.S.C. § 3551 et seq., Public Law (P.L.) 113-283.",
            "NIST is responsible.",
        ],
    ),
    "equation_references": (
        (
            "The approximation error (Eq. (8)). In practice, Eq. (4) is approximated. "
            "Revisiting Eq. (8), we stop."
        ),
        [
            "The approximation error (Eq. (8)).",
            "In practice, Eq. (4) is approximated.",
            "Revisiting Eq. (8), we stop.",
        ],
    ),
    "latin_and_titles": (
        "Also cf. Smith on this. Dr. Smith and Prof. Jones met. See No. 5 and Vol. 3 here.",
        ["Also cf. Smith on this.", "Dr. Smith and Prof. Jones met.", "See No. 5 and Vol. 3 here."],
    ),
    "may_end_abbreviation_before_capital_splits": (
        "We bought apples, pears, etc. Then we left. The firm Acme Inc. Its revenue grew.",
        [
            "We bought apples, pears, etc.",
            "Then we left.",
            "The firm Acme Inc.",
            "Its revenue grew.",
        ],
    ),
    "may_end_abbreviation_before_lowercase_stays": (
        "We bought apples, pears, etc. and then we left.",
        ["We bought apples, pears, etc. and then we left."],
    ),
    "one_letter_variable_is_a_boundary": (
        "Let X be a chain with transition kernel P. Its measure is finite.",
        ["Let X be a chain with transition kernel P.", "Its measure is finite."],
    ),
    "appendix_letter_is_a_boundary": (
        "For proofs, see Appendix A. This fact uses two properties.",
        ["For proofs, see Appendix A.", "This fact uses two properties."],
    ),
    "initial_after_bracket_is_not": (
        "This was shown before (P. Smith, 2020) in detail. Next one.",
        ["This was shown before (P. Smith, 2020) in detail.", "Next one."],
    ),
    "section_number_heading": ("2.1. Experimental Design", ["2.1. Experimental Design"]),
    "section_number_run_in_heading": (
        "3.1. The marginals. We fit each one.",
        ["3.1. The marginals.", "We fit each one."],
    ),
    "initials_run_with_hyphen": (
        "[3] K. Marchisio, W. Q. Leong, S. Ruder, W. -Y. Lee, and B. Tan, “Global MMLU,” 2024.",
        ["[3] K. Marchisio, W. Q. Leong, S. Ruder, W. -Y. Lee, and B. Tan, “Global MMLU,” 2024."],
    ),
    "reference_marker_initials": (
        "[9] R. Ng, T. N. Nguyen, N. C. Tai, and Y. Susanto, “SEA-LION,” 2024. [10] A. Zou.",
        ["[9] R. Ng, T. N. Nguyen, N. C. Tai, and Y. Susanto, “SEA-LION,” 2024.", "[10] A. Zou."],
    ),
    "closing_quote_stays_with_sentence": (
        "He said “stop.” Then he left.",
        ["He said “stop.”", "Then he left."],
    ),
    "closing_quote_alone_after_split": (
        "The motto was “Move fast.\n” It worked for a while.",
        ["The motto was “Move fast.\n”", "It worked for a while."],
    ),
    "list_marker_inside_sentence": (
        (
            "For a vertex i, we write PA (i), CH (i) for its parents. "
            "A small model (System\n1) scans raw context."
        ),
        [
            "For a vertex i, we write PA (i), CH (i) for its parents.",
            "A small model (System\n1) scans raw context.",
        ],
    ),
    "numbered_list_items_stay_split": (
        "1. Maintained peak habits\n2. Stabilized the team\n3. Raised funds",
        ["1. Maintained peak habits", "2. Stabilized the team", "3. Raised funds"],
    ),
    "reference_after_real_end_stays_split": (
        "If you cannot decide, the answer is no. [10] Our bodies know.",
        ["If you cannot decide, the answer is no.", "[10] Our bodies know."],
    ),
    "real_list_item_stays_split": (
        "Property\n(i) generalizes to any density, and\n(ii) generalizes only under a condition.",
        [
            "Property",
            "(i) generalizes to any density, and",
            "(ii) generalizes only under a condition.",
        ],
    ),
}


@pytest.mark.parametrize("case", sorted(CASES))
def test_ing5_boundary_rules(case: str) -> None:
    text, expected = CASES[case]
    assert _texts(text) == expected


@pytest.mark.parametrize("case", sorted(CASES))
def test_ing5_boundary_rules_offsets_round_trip(case: str) -> None:
    block = _block(CASES[case][0])
    segments = split_sentences(block, document_id=0, order_start=0, id_start=0)
    for s in segments:
        assert block.text[s.char_start : s.char_end] == s.text
        assert s.text == s.text.strip()
    starts = [s.char_start for s in segments]
    assert starts == sorted(starts)
    assert all(a.char_end <= b.char_start for a, b in itertools.pairwise(segments))


def test_ing5_per_document_abbreviation_extension() -> None:
    extra = DEFAULT_ABBREVIATIONS.extended(non_terminal={"xyzzy."})
    block = _block("The Xyzzy. Quux report was read. It helped.")
    out = split_sentences(block, document_id=0, order_start=0, id_start=0, abbreviations=extra)
    assert [s.text for s in out] == ["The Xyzzy. Quux report was read.", "It helped."]


def test_ing5_split_inside_a_token_is_kept_split_before_punctuation_is_undone() -> None:
    """pysbd's mid-token splits ("PA" | "(i)") stay (D14 golden); "seq." | ", P" is undone."""
    from hearnarro.ingestion.segment import _merge

    text = "we write PA(i), CH(i) for its parents."
    cut = text.index("(i), CH")
    assert _merge(text, [(0, cut), (cut, len(text))], DEFAULT_ABBREVIATIONS) == [
        (0, cut),
        (cut, len(text)),
    ]
    text = "44 U.S.C. § 3551 et seq., Public Law 113-283."
    cut = text.index(", Public")
    assert _merge(text, [(0, cut), (cut, len(text))], DEFAULT_ABBREVIATIONS) == [(0, len(text))]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Visit shopping.com for details.", ["Visit shopping.com for details."]),
        ("see vast.com. Then go.", ["see vast.com.", "Then go."]),
        (
            "Read my blog at www. ericpartaker.com, but not today.",
            ["Read my blog at www. ericpartaker.com, but not today."],
        ),
    ],
)
def test_ing5_domain_dot_is_not_a_sentence_end(text: str, expected: list[str]) -> None:
    segments = split_sentences(_block(text), document_id=3, order_start=0, id_start=0)
    assert [s.text for s in segments] == expected


def _item(text: str) -> LogicalBlock:
    return LogicalBlock(id=3, page=0, type="list", text=text, source=[(0, 0)])


@pytest.mark.parametrize(
    "text",
    [
        "→ Questions nearly everything",
        "→ And…doesn’t take himself too goddamn seriously.",
        "• Text accuracy (Scoretext): The accuracy of the target LLM.",
        "→ 1974 - Born in Delhi, India",
    ],
)
def test_ing5_list_item_is_one_segment_glyph_silent(text: str) -> None:
    (seg,) = split_sentences(_item(text), document_id=1, order_start=0, id_start=0)
    assert seg.text == text
    assert (seg.char_start, seg.char_end) == (0, len(text))
    assert seg.normalized_text == text[2:]
    assert seg.char_map[0] == 2


def test_ing5_list_item_with_inner_sentence_end_splits() -> None:
    text = "→ Total honesty at all times. It’s almost always possible to be honest."
    segs = split_sentences(_item(text), document_id=1, order_start=0, id_start=0)
    assert [s.text for s in segs] == [
        "→ Total honesty at all times.",
        "It’s almost always possible to be honest.",
    ]
    assert segs[0].normalized_text == "Total honesty at all times."
    for s in segs:
        assert text[s.char_start : s.char_end] == s.text


def test_ing5_numbered_item_keeps_marker_spoken() -> None:
    (seg,) = split_sentences(_item("1. First step"), document_id=1, order_start=0, id_start=0)
    assert seg.normalized_text == "1. First step"
