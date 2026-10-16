"""End-to-end ingestion: PDF -> pages -> logical blocks -> segments."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from hearnarro.ingestion.models import LogicalBlock, Page, Segment


@dataclass
class IngestResult:
    pages: list[Page]
    blocks: list[LogicalBlock]
    segments: list[Segment]


def ingest(pdf_path: str | Path, *, document_id: int = 0, ocr: bool = True) -> IngestResult:
    """extract_pages -> classify_pages -> order_document -> merge_blocks -> split_sentences."""
    raise NotImplementedError
