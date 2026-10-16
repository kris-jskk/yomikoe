"""Stage 2: classify blocks by type (ING-3).

Rules from docs/TECHNICAL_DESIGN.md stage 2, first match wins:
header/footer, heading, caption, footnote, table, equation, list, body.
"""

from __future__ import annotations

import math
import re
from collections import defaultdict

from hearnarro.ingestion.models import BBox, Block, BlockType, Page

PAGE_NUMBER_RE = re.compile(r"^(?:\d+|page\s+\d+\b.*|\d+\s+of\s+\d+)$", re.IGNORECASE)
CAPTION_RE = re.compile(r"^(?:Figure|Fig\.|Table|Listing)\s*\d")
LIST_RE = re.compile(r"^(?:[•·▪‣◦\-–*]|\d+[.)])\s")
MATH_CHARS = set("=+−-×÷∑∫√∂∞≤≥≈∝∈∀∃αβγδεθλμπσφω^_{}|")
MATH_FONT_MARKERS = ("Math", "CMSY", "CMMI", "CMEX")

BAND_FRAC = 0.08
HEADING_SIZE_RATIO = 1.15
HEADING_MAX_WORDS = 12
CAPTION_MAX_DIST = 40.0
FOOTNOTE_SIZE_RATIO = 0.85
FOOTNOTE_TOP_FRAC = 0.75


def normalize_key(text: str) -> str:
    """Lowercase, collapse whitespace, strip. Digits are kept."""
    return " ".join(text.lower().split())


def body_median_size(pages: list[Page]) -> float:
    """Median span size across the document, each span weighted by len(text)."""
    weighted = sorted(
        (s.size, len(s.text))
        for p in pages
        for b in p.blocks
        for ln in b.lines
        for s in ln.spans
        if s.text
    )
    total = sum(w for _, w in weighted)
    if total == 0:
        return 0.0
    half = total / 2
    acc = 0
    for size, w in weighted:
        acc += w
        if acc >= half:
            return size
    return weighted[-1][0]


def _band(block: Block, page: Page, band_frac: float) -> str | None:
    if block.bbox.y1 <= band_frac * page.height:
        return "top"
    if block.bbox.y0 >= (1 - band_frac) * page.height:
        return "bottom"
    return None


def repeated_band_texts(
    pages: list[Page], *, band_frac: float = BAND_FRAC, min_pages: int = 3
) -> set[str]:
    """normalize_key of top/bottom-band blocks that recur on >= min_pages distinct pages."""
    seen: dict[str, set[int]] = defaultdict(set)
    for page in pages:
        for block in page.blocks:
            if _band(block, page, band_frac) is None:
                continue
            key = normalize_key(block.text)
            if key:
                seen[key].add(page.number)
    return {k for k, nums in seen.items() if len(nums) >= min_pages}


def _distance(a: BBox, b: BBox) -> float:
    dx = max(0.0, a.x0 - b.x1, b.x0 - a.x1)
    dy = max(0.0, a.y0 - b.y1, b.y0 - a.y1)
    return math.hypot(dx, dy)


def _max_size(block: Block) -> float:
    return max((s.size for ln in block.lines for s in ln.spans), default=0.0)


def _bold_majority(block: Block) -> bool:
    spans = [s for ln in block.lines for s in ln.spans]
    total = sum(len(s.text.strip()) for s in spans)
    bold = sum(len(s.text.strip()) for s in spans if s.bold)
    return total > 0 and bold * 2 > total


def _is_equation(block: Block) -> bool:
    total = 0
    math_chars = 0
    for ln in block.lines:
        for s in ln.spans:
            math_font = any(m in s.font for m in MATH_FONT_MARKERS)
            for ch in s.text:
                if ch.isspace():
                    continue
                total += 1
                if math_font or ch in MATH_CHARS:
                    math_chars += 1
    return total > 0 and math_chars * 2 > total


def _starts_with_superscript_digit(block: Block) -> bool:
    for ln in block.lines:
        for s in ln.spans:
            if s.text.strip():
                return s.superscript and s.text.strip()[0].isdigit()
    return False


def _classify(block: Block, page: Page, median: float, repeated: set[str]) -> BlockType:
    text = block.text.strip()
    band = _band(block, page, BAND_FRAC)
    if band is not None and (normalize_key(text) in repeated or PAGE_NUMBER_RE.match(text)):
        return "header" if band == "top" else "footer"
    if not text:
        return "body"
    size = _max_size(block)
    if median > 0 and size >= HEADING_SIZE_RATIO * median:
        return "heading"
    if _bold_majority(block) and len(text.split()) <= HEADING_MAX_WORDS and not text.endswith("."):
        return "heading"
    if CAPTION_RE.match(text) and any(
        _distance(block.bbox, other) <= CAPTION_MAX_DIST
        for other in [*page.image_bboxes, *page.table_bboxes]
    ):
        return "caption"
    if (
        median > 0
        and size <= FOOTNOTE_SIZE_RATIO * median
        and block.bbox.y0 >= FOOTNOTE_TOP_FRAC * page.height
    ) or _starts_with_superscript_digit(block):
        return "footnote"
    if any(block.bbox.overlaps(t) for t in page.table_bboxes):
        return "table"
    if _is_equation(block):
        return "equation"
    if LIST_RE.match(block.lines[0].text.strip()):
        return "list"
    return "body"


def classify_pages(pages: list[Page]) -> list[Page]:
    """Set block.type in place (first matching rule wins) and return pages."""
    median = body_median_size(pages)
    repeated = repeated_band_texts(pages)
    for page in pages:
        for block in page.blocks:
            block.type = _classify(block, page, median, repeated)
    return pages
