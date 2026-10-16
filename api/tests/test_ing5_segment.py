"""Stage 5, sentence segmentation with offsets (D4, ING-5)."""

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
