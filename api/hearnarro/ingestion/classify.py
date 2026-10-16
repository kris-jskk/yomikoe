"""Stage 2: classify blocks by type (ING-3)."""

from __future__ import annotations

import re

from hearnarro.ingestion.models import Page

PAGE_NUMBER_RE = re.compile(r"^(?:\d+|page\s+\d+\b.*|\d+\s+of\s+\d+)$", re.IGNORECASE)


def normalize_key(text: str) -> str:
    """Lowercase, collapse whitespace, strip. Digits are kept."""
    raise NotImplementedError


def body_median_size(pages: list[Page]) -> float:
    """Median span size across the document, each span weighted by len(text)."""
    raise NotImplementedError


def repeated_band_texts(
    pages: list[Page], *, band_frac: float = 0.08, min_pages: int = 3
) -> set[str]:
    """normalize_key of top/bottom-band blocks that recur on >= min_pages distinct pages."""
    raise NotImplementedError


def classify_pages(pages: list[Page]) -> list[Page]:
    """Set block.type in place (first matching rule wins) and return pages."""
    raise NotImplementedError
