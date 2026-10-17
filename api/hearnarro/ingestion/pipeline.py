"""End-to-end ingestion: PDF -> pages -> logical blocks -> segments."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from hearnarro.ingestion.acronyms import document_definitions
from hearnarro.ingestion.classify import classify_pages
from hearnarro.ingestion.extract import extract_pages
from hearnarro.ingestion.mathspeak import apply_mathspeak
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
from hearnarro.ingestion.profile import PROSE_DEFAULT, DocumentProfile, compute_profile
from hearnarro.ingestion.segment import split_sentences


@dataclass
class IngestResult:
    pages: list[Page]
    blocks: list[LogicalBlock]
    segments: list[Segment]
    acronyms: dict[str, str] = field(default_factory=dict)  # {ACR: expansion}, ING-6
    ocr_skipped_pages: int = 0  # pages that needed OCR while no engine was available (ING-2)
    profile: DocumentProfile = PROSE_DEFAULT  # ING-11, D40: computed between stages 4 and 5


def ingest(
    pdf_path: str | Path,
    *,
    document_id: int = 0,
    ocr: bool = True,
    on_page: Callable[[int, int], None] | None = None,
    ocr_backend: OCRBackend | None | _Default = DEFAULT_OCR,
) -> IngestResult:
    """extract_pages -> classify_pages -> order_document -> merge_blocks -> compute_profile
    -> split_sentences -> apply_mathspeak; the profile (ING-11, D40) is computed on the merged blocks and passed
    to stage 5, whose normalizer needs the class for the bracket rule;
    acronym definitions are collected from the merged block texts (stage 5); mathspeak
    (MATH-1..4) then rewrites the segments holding maths and stores their ``math_json``.

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
    profile = compute_profile(pages, blocks)  # ING-11, between stage 4 and stage 5
    segments: list[Segment] = []
    for block in blocks:
        segments.extend(
            split_sentences(
                block,
                document_id=document_id,
                order_start=len(segments),
                id_start=len(segments),
                profile=profile,
            )
        )
    # MATH-1..4, D36, D37 (spec m5 §2b, §3b): maths spans spoken, Segment.math_json filled.
    apply_mathspeak(segments, blocks, pages, profile)
    return IngestResult(
        pages=pages,
        blocks=blocks,
        segments=segments,
        acronyms=document_definitions(b.text for b in blocks),
        ocr_skipped_pages=skipped,
        profile=profile,
    )
