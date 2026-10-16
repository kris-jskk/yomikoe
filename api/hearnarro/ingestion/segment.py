"""Stage 5: sentence segmentation with offsets into the logical block (D4, ING-5)."""

from __future__ import annotations

from hearnarro.ingestion.models import LogicalBlock, Segment


def split_sentences(
    block: LogicalBlock, *, document_id: int, order_start: int, id_start: int
) -> list[Segment]:
    """Split block.text into sentence Segments; text == block.text[char_start:char_end]."""
    raise NotImplementedError
