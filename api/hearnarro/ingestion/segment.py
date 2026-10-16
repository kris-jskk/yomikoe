"""Stage 5: sentence segmentation with offsets into the logical block (D4, ING-5)."""

from __future__ import annotations

from functools import cache

import pysbd

from hearnarro.ingestion.models import LogicalBlock, Segment
from hearnarro.ingestion.normalize import normalize


@cache
def _segmenter() -> pysbd.Segmenter:
    return pysbd.Segmenter(language="en", clean=False, char_span=True)


def _locate(text: str, sent: str, hint: int, cursor: int) -> int:
    """Start of ``sent`` in ``text``: pysbd's offset when it round-trips, else search."""
    if hint >= cursor and text[hint : hint + len(sent)] == sent:
        return hint
    return text.find(sent, cursor)


def split_sentences(
    block: LogicalBlock, *, document_id: int, order_start: int, id_start: int
) -> list[Segment]:
    """Split block.text into sentence Segments; text == block.text[char_start:char_end]."""
    text = block.text
    if not text.strip():
        return []
    segments: list[Segment] = []
    cursor = 0
    for span in _segmenter().segment(text):
        raw = span.sent
        sent = raw.strip()
        if not sent:
            continue
        hint = span.start + (len(raw) - len(raw.lstrip()))
        start = _locate(text, sent, hint, cursor)
        if start < 0:
            raise ValueError(f"block {block.id}: sentence offsets do not round-trip: {sent!r}")
        end = start + len(sent)
        if text[start:end] != sent:
            raise ValueError(f"block {block.id}: sentence offsets do not round-trip: {sent!r}")
        cursor = end
        normalized, char_map = normalize(sent)
        i = len(segments)
        segments.append(
            Segment(
                id=id_start + i,
                document_id=document_id,
                block_id=block.id,
                order=order_start + i,
                section_id=None,
                text=sent,
                normalized_text=normalized,
                char_start=start,
                char_end=end,
                char_map=char_map,
            )
        )
    return segments
