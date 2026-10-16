"""End-to-end ingestion: PDF -> pages -> logical blocks -> segments."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from hearnarro.ingestion.classify import classify_pages
from hearnarro.ingestion.extract import extract_pages
from hearnarro.ingestion.merge import merge_blocks
from hearnarro.ingestion.models import LogicalBlock, Page, Segment
from hearnarro.ingestion.order import order_document
from hearnarro.ingestion.segment import split_sentences


@dataclass
class IngestResult:
    pages: list[Page]
    blocks: list[LogicalBlock]
    segments: list[Segment]


def ingest(pdf_path: str | Path, *, document_id: int = 0, ocr: bool = True) -> IngestResult:
    """extract_pages -> classify_pages -> order_document -> merge_blocks -> split_sentences."""
    pages = classify_pages(extract_pages(pdf_path, ocr=ocr))
    blocks = merge_blocks(order_document(pages))
    segments: list[Segment] = []
    for block in blocks:
        segments.extend(
            split_sentences(
                block,
                document_id=document_id,
                order_start=len(segments),
                id_start=len(segments),
            )
        )
    return IngestResult(pages=pages, blocks=blocks, segments=segments)
