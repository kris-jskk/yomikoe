"""End-to-end ingestion: PDF -> pages -> logical blocks -> segments."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from hearnarro.ingestion.acronyms import document_definitions
from hearnarro.ingestion.classify import classify_pages
from hearnarro.ingestion.extract import extract_pages
from hearnarro.ingestion.merge import merge_blocks
from hearnarro.ingestion.models import LogicalBlock, Page, Segment
from hearnarro.ingestion.ocr import (
    DEFAULT_OCR,
    OCRBackend,
    _Default,
    apply_ocr,
    default_backend,
)
from hearnarro.ingestion.order import order_document
from hearnarro.ingestion.segment import split_sentences


@dataclass
class IngestResult:
    pages: list[Page]
    blocks: list[LogicalBlock]
    segments: list[Segment]
    acronyms: dict[str, str] = field(default_factory=dict)  # {ACR: expansion}, ING-6
    ocr_skipped_pages: int = 0  # pages that needed OCR while no engine was available (ING-2)


def ingest(
    pdf_path: str | Path,
    *,
    document_id: int = 0,
    ocr: bool = True,
    on_page: Callable[[int, int], None] | None = None,
    ocr_backend: OCRBackend | None | _Default = DEFAULT_OCR,
) -> IngestResult:
    """extract_pages -> classify_pages -> order_document -> merge_blocks -> split_sentences;
    acronym definitions are collected from the merged block texts (stage 5).

    ``on_page(pages_done, total)`` is forwarded to ``extract_pages``; it does not change the
    result.

    OCR (ING-2, D28): pages that ``needs_ocr`` go to ``ocr_backend``. Omitted, it is the default
    engine (tesseract if on PATH, else none); ``None`` means no engine; ``ocr=False`` disables
    OCR. Pages left empty for want of an engine are counted in ``ocr_skipped_pages``.
    """
    backend = default_backend() if isinstance(ocr_backend, _Default) else ocr_backend
    pages = extract_pages(pdf_path, ocr=False, on_page=on_page)
    skipped = 0
    if ocr:
        pages, skipped = apply_ocr(pdf_path, pages, backend)
    pages = classify_pages(pages)
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
    return IngestResult(
        pages=pages,
        blocks=blocks,
        segments=segments,
        acronyms=document_definitions(b.text for b in blocks),
        ocr_skipped_pages=skipped,
    )
