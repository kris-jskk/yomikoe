"""Stage 1: extract spans from a PDF, OCR pages without a text layer (D1, ING-2)."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

from hearnarro.ingestion.models import BBox, Page


class OCRUnavailable(RuntimeError):
    """Raised when OCR is required but pytesseract or the tesseract binary is missing."""


def ocr_available() -> bool:
    """True when pytesseract is importable AND the tesseract binary is on PATH."""
    raise NotImplementedError


def page_from_dict(
    number: int,
    width: float,
    height: float,
    text_dict: dict[str, Any],
    image_bboxes: Sequence[BBox] = (),
    table_bboxes: Sequence[BBox] = (),
) -> Page:
    """Build a Page from a PyMuPDF ``page.get_text("dict")`` payload (pure)."""
    raise NotImplementedError


def extract_pages(
    pdf_path: str | Path, *, ocr: bool = True, min_text_chars: int = 20
) -> list[Page]:
    """Extract every page of ``pdf_path``; OCR pages with fewer than ``min_text_chars``."""
    raise NotImplementedError
