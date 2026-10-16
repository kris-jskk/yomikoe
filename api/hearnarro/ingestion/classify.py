"""Stage 2: classify blocks by type (ING-3).

Rules from docs/TECHNICAL_DESIGN.md stage 2, first match wins:
noise (rotated text), header/footer, noise (boilerplate text), heading, caption, footnote,
table, equation, list, body. Then (D12) any block but a caption whose bbox lies at least
FIGURE_INSIDE_FRAC inside a figure region (Page.figure_bboxes) is typed figure. Two document
passes follow: cover-page pull quotes typed heading by size become body, and a table of
contents (a "Contents" heading and the TOC-like blocks after it) is typed toc (never read).
"""

from __future__ import annotations

import math
import re
import unicodedata
from collections import defaultdict

from hearnarro.ingestion.models import BBox, Block, BlockType, Page

PAGE_NUMBER_RE = re.compile(
    r"^(?:\d+|[ivxlc]+|page\s+(?:\d+|[ivxlc]+)\b.*|\d+\s+of\s+\d+)$", re.IGNORECASE
)
EMAIL = r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"
URL = r"(?:https?://|www\.)\S+"
# A line whose only content is emails/URLs (comma, semicolon or space separated).
CONTACT_ONLY_RE = re.compile(rf"^(?:{EMAIL}|{URL})(?:[\s,;]+(?:{EMAIL}|{URL}))*[\s,;.]*$")
# Text that is never read aloud wherever it appears.
BOILERPLATE_RE = re.compile(
    r"^(?:preprint\.?|under review\.?|this publication is available free of charge from:?.*)$",
    re.IGNORECASE,
)
# Cover-page signature block of NIST-style reports (agency, secretary, director).
SIGNATURE_RE = re.compile(r"Department of Commerce|\bSecretary\b|\bDirector\b")
RULE_RE = re.compile(r"^[_\-–—=\s]{5,}$")
CAPTION_RE = re.compile(r"^(?:Figure|Fig\.|Table|Listing)\s*\d")
LIST_RE = re.compile(r"^(?:[•·▪‣◦\-–*]|\d+[.)])\s")
MATH_CHARS = set("=+−-×÷∑∫√∂∞≤≥≈∝∈∀∃αβγδεθλμπσφω^_{}|")
MATH_FONT_MARKERS = ("Math", "CMSY", "CMMI", "CMEX", "CMBSY", "MSBM", "MSAM", "RSFS", "EUFM")
EQ_NUMBER_RE = re.compile(r"^\(\d+[a-z]?\)[.,]?$")
SCRIPT_RATIO = 0.8  # text smaller than this share of the block's largest size is a script
EQ_PROSE_LETTERS: float | None = 0.5
TABLE_FIRST = True  # a block centred inside a table region is table before heading/caption

BAND_FRAC = 0.08
HEADING_SIZE_RATIO = 1.15
HEADING_MAX_WORDS = 12
CAPTION_MAX_DIST = 40.0
FOOTNOTE_SIZE_RATIO = 0.85
FOOTNOTE_TOP_FRAC = 0.75
# A block opening with a superscript digit is a footnote only below this share of the page
# height; above it, it is an affiliation line under the authors (tuned 2026-10-16).
SUPERSCRIPT_FOOTNOTE_TOP_FRAC = 0.5
FOOTNOTE_MIN_CHARS = 3  # 1-3 char small blocks are equation sub/superscripts, not footnotes
BAND_UPPER_RATIO = 0.6
BAND_SMALL_RATIO = 0.95
BAND_MAX_LINES = 3
COVER_PAGES = 2
MARGIN_FRAC = 0.10
SIGNATURE_TOP_FRAC = 0.70
FIGURE_INSIDE_FRAC = 0.80  # share of a block's area inside a figure region to be figure text

# Table of contents (ING-3, type toc; found on a user PDF 2026-10-16).
TOC_HEADING_RE = re.compile(r"^(?:table of )?contents$")
LEADER_RE = re.compile(r"^[\s.·…]+$")
LEADER_MIN_DOTS = 3
TOC_PAGE_NUMBER_RE = re.compile(r"\d{1,4}\s*$")
TOC_INNER_NUMBER_RE = re.compile(r"(?<=\s)\d{1,4}(?=\s)")  # "3 Title 6 Title 9 Title"
TOC_LINE_SHARE = 0.5
TOC_MAX_PAGES = 6
TOC_LEAD_MAX_LINES = 2  # a short non-TOC-like block before the first TOC line (entry title)
# Cover pages: a digit-free table region with at most this many lines is a title, not a table.
COVER_TABLE_MAX_LINES = 4
EQUATION_PUNCT = set(".,;:!?")
OPENING_QUOTES = '“"‘«„'
SENTENCE_END_RE = re.compile(r"[a-z]{2,}[.!?][\"”’)]*(?=\s|$)")
PULL_QUOTE_MIN_SENTENCES = 2


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


def _is_math_font(font: str) -> bool:
    return any(m in font for m in MATH_FONT_MARKERS)


def _is_equation(block: Block) -> bool:
    """Display-equation text (ING-3): math glyphs (math font or MATH_CHARS) are the majority;
    or (tuned 2026-10-16 on pdfplumber) the block holds a math-font glyph and its prose letters
    (text-font letters at no less than SCRIPT_RATIO of the block's largest size) are under
    EQ_PROSE_LETTERS of its non-space characters; or it is a bare equation number."""
    text = "".join(block.text.split())
    if EQ_NUMBER_RE.match(text):
        return True
    top = _max_size(block)
    total = 0
    math_chars = 0
    prose_letters = 0
    has_math_font = False
    for ln in block.lines:
        for s in ln.spans:
            math_font = _is_math_font(s.font)
            has_math_font = has_math_font or (math_font and bool(s.text.strip()))
            for ch in s.text:
                if ch.isspace():
                    continue
                total += 1
                if math_font or ch in MATH_CHARS:
                    math_chars += 1
                elif ch.isalpha() and s.size >= SCRIPT_RATIO * top:
                    prose_letters += 1
    if total == 0:
        return False
    if math_chars * 2 > total:
        return True
    return (
        EQ_PROSE_LETTERS is not None and has_math_font and prose_letters < EQ_PROSE_LETTERS * total
    )


def _starts_with_superscript_digit(block: Block) -> bool:
    for ln in block.lines:
        for s in ln.spans:
            if s.text.strip():
                return s.superscript and s.text.strip()[0].isdigit()
    return False


def _band_mid(block: Block, page: Page) -> str | None:
    """Band by vertical midpoint: catches a header whose rule line pokes out of the band."""
    if block.bbox.y_mid <= BAND_FRAC * page.height:
        return "top"
    if block.bbox.y_mid >= (1 - BAND_FRAC) * page.height:
        return "bottom"
    return None


def _in_band_mid(block: Block, page: Page) -> bool:
    return _band_mid(block, page) is not None


def _is_margin_stamp(block: Block, page: Page) -> bool:
    """Rotated text (any line not left-to-right) in the outer MARGIN_FRAC of the page.

    Rotated text inside the page (figure axis labels) is left to the other rules.
    """
    in_margin = (
        block.bbox.x1 <= MARGIN_FRAC * page.width or block.bbox.x0 >= (1 - MARGIN_FRAC) * page.width
    )
    return in_margin and any(
        abs(ln.dir[0] - 1.0) > 0.01 or abs(ln.dir[1]) > 0.01
        for ln in block.lines
        if ln.text.strip()
    )


def _looks_like_running_header(block: Block, text: str, median: float) -> bool:
    """Band block that is short and either mostly upper-case or smaller than body text."""
    lines = [ln.text.strip() for ln in block.lines if ln.text.strip()]
    if not lines or len(lines) > BAND_MAX_LINES:
        return False
    letters = [c for c in text if c.isalpha()]
    if letters and sum(c.isupper() for c in letters) >= BAND_UPPER_RATIO * len(letters):
        return True
    return median > 0 and _max_size(block) <= BAND_SMALL_RATIO * median


def _is_leader_line(line: str) -> bool:
    return LEADER_RE.match(line) is not None and sum(c in ".·…" for c in line) >= LEADER_MIN_DOTS


def _is_punctuation_only(text: str) -> bool:
    """Only punctuation (quotes, dashes, asterisks...). A bare ``.`` ``,`` ``!`` etc. is
    left to the equation rule: it trails a display equation or is a factorial."""
    chars = [c for c in text if not c.isspace()]
    if not chars or all(c in EQUATION_PUNCT for c in chars):
        return False
    return all(unicodedata.category(c).startswith("P") for c in chars)


def _is_noise_text(block: Block, page: Page) -> bool:
    lines = [" ".join(ln.text.split()) for ln in block.lines if ln.text.strip()]
    if not lines:
        return False
    if all(_is_leader_line(ln) for ln in lines) or _is_punctuation_only(" ".join(lines)):
        return True  # TOC leader dots; a stray closing quote or dash (found on a user PDF)
    if all(CONTACT_ONLY_RE.match(ln) or BOILERPLATE_RE.match(ln) for ln in lines):
        return True
    if all(RULE_RE.match(ln) for ln in lines):
        return True
    tokens = " ".join(lines).split()
    if len(tokens) >= 6 and all(len(t) == 1 and t.isalpha() for t in tokens):
        return True  # letter-spaced banner, e.g. "C O M P U T E R   S E C U R I T Y"
    return (
        page.number < COVER_PAGES
        and block.bbox.y0 >= SIGNATURE_TOP_FRAC * page.height
        and SIGNATURE_RE.search(" ".join(lines)) is not None
    )


def _classify(
    block: Block, page: Page, median: float, repeated: set[str], tables: list[BBox]
) -> BlockType:
    text = block.text.strip()
    if _is_margin_stamp(block, page):
        return "noise"
    band = _band(block, page, BAND_FRAC) or _band_mid(block, page)
    if band is not None and (
        normalize_key(text) in repeated
        or PAGE_NUMBER_RE.match(text)
        or (_in_band_mid(block, page) and _looks_like_running_header(block, text, median))
    ):
        return "header" if band == "top" else "footer"
    if not text:
        return "body"
    if _is_noise_text(block, page):
        return "noise"
    if TABLE_FIRST and _inside(block, tables):
        return "table"
    size = _max_size(block)
    if median > 0 and size >= HEADING_SIZE_RATIO * median:
        return "heading"
    if _bold_majority(block) and len(text.split()) <= HEADING_MAX_WORDS and not text.endswith("."):
        return "heading"
    if CAPTION_RE.match(text) and any(
        _distance(block.bbox, other) <= CAPTION_MAX_DIST for other in [*page.image_bboxes, *tables]
    ):
        return "caption"
    if (
        median > 0
        and size <= FOOTNOTE_SIZE_RATIO * median
        and block.bbox.y0 >= FOOTNOTE_TOP_FRAC * page.height
        and len("".join(text.split())) > FOOTNOTE_MIN_CHARS
    ) or (
        _starts_with_superscript_digit(block)
        and block.bbox.y0 >= SUPERSCRIPT_FOOTNOTE_TOP_FRAC * page.height
    ):
        return "footnote"
    if any(block.bbox.overlaps(t) for t in tables):
        return "table"
    if _is_equation(block):
        return "equation"
    if LIST_RE.match(block.lines[0].text.strip()):
        return "list"
    return "body"


def _inter_area(a: BBox, b: BBox) -> float:
    w = min(a.x1, b.x1) - max(a.x0, b.x0)
    h = min(a.y1, b.y1) - max(a.y0, b.y0)
    return max(0.0, w) * max(0.0, h)


def _inside(block: Block, regions: list[BBox]) -> bool:
    """The block's centre lies inside one region."""
    x, y = block.bbox.x_mid, block.bbox.y_mid
    return any(r.x0 <= x <= r.x1 and r.y0 <= y <= r.y1 for r in regions)


def in_figure(block: Block, regions: list[BBox]) -> bool:
    """``block`` lies at least FIGURE_INSIDE_FRAC (by area) inside one region (D12).

    A zero-area block counts when it lies wholly inside a region.
    """
    b = block.bbox
    area = max(0.0, b.width) * max(0.0, b.height)
    if area <= 0:
        return any(r.x0 <= b.x0 and b.x1 <= r.x1 and r.y0 <= b.y0 and b.y1 <= r.y1 for r in regions)
    return any(_inter_area(b, r) >= FIGURE_INSIDE_FRAC * area for r in regions)


def _cover_tables(page: Page, median: float) -> list[BBox]:
    """Table regions to use on ``page``. On page 0 a region whose blocks hold no digit, at most
    COVER_TABLE_MAX_LINES lines in all, and are all set at heading size is a ruled title frame,
    not a table (ING-3)."""
    if page.number != 0:
        return page.table_bboxes
    kept = []
    for region in page.table_bboxes:
        members = [b for b in page.blocks if _inside(b, [region]) or b.bbox.overlaps(region)]
        lines = sum(1 for b in members for ln in b.lines if ln.text.strip())
        title_sized = median > 0 and all(
            _max_size(b) >= HEADING_SIZE_RATIO * median for b in members
        )
        has_digit = any(c.isdigit() for b in members for c in b.text)
        if has_digit or lines > COVER_TABLE_MAX_LINES or not members or not title_sized:
            kept.append(region)
    return kept


def _retype_pull_quotes(page: Page, median: float) -> None:
    """On a cover page, a run of consecutive blocks typed heading by the size rule whose joined
    text starts with an opening quote or holds PULL_QUOTE_MIN_SENTENCES sentence ends is a
    pull quote: each block becomes body (ING-3)."""
    run: list[Block] = []
    for block in [*page.blocks, None]:
        if (
            block is not None
            and block.type == "heading"
            and median > 0
            and _max_size(block) >= HEADING_SIZE_RATIO * median
        ):
            run.append(block)
            continue
        text = " ".join(" ".join(b.text.split()) for b in run)
        if run and (
            text.startswith(tuple(OPENING_QUOTES))
            or len(SENTENCE_END_RE.findall(text)) >= PULL_QUOTE_MIN_SENTENCES
        ):
            for b in run:
                b.type = "body"
        run = []


def _toc_like(block: Block) -> bool:
    lines = [" ".join(ln.text.split()) for ln in block.lines if ln.text.strip()]
    if not lines:
        return False
    if len(lines) == 1 and _is_leader_line(lines[0]):
        return True
    hits = sum(
        1
        for ln in lines
        if _is_leader_line(ln)
        or TOC_PAGE_NUMBER_RE.search(ln)
        or len(TOC_INNER_NUMBER_RE.findall(ln)) >= 2
    )
    return hits >= TOC_LINE_SHARE * len(lines)


def _mark_toc(pages: list[Page], median: float) -> None:
    """A heading reading "Contents" or "Table of contents" opens a TOC region; it runs over the
    TOC-like blocks after it, across pages, and ends at the first other block once one TOC-like
    block was seen, at a body-size-or-larger heading, or after TOC_MAX_PAGES pages. Short blocks
    before the first TOC-like one join it. A region with no TOC-like block types nothing (ING-3).
    """
    region: list[Block] = []
    seen = False
    start = 0

    def close() -> None:
        nonlocal region, seen
        if seen:
            for b in region:
                b.type = "toc"
        region, seen = [], False

    for page in pages:
        if region and page.number - start >= TOC_MAX_PAGES:
            close()
        for block in page.blocks:
            if block.type in ("header", "footer", "figure", "image") or not block.text.strip():
                continue
            if region:
                lines = [ln for ln in block.lines if ln.text.strip()]
                if _toc_like(block):
                    region.append(block)
                    seen = True
                    continue
                big_heading = block.type == "heading" and _max_size(block) >= median
                if not seen and not big_heading and len(lines) <= TOC_LEAD_MAX_LINES:
                    region.append(block)
                    continue
                close()
            if block.type == "heading" and TOC_HEADING_RE.match(normalize_key(block.text)):
                region, seen, start = [block], False, page.number
    close()


def classify_pages(pages: list[Page]) -> list[Page]:
    """Set block.type in place (first matching rule wins) and return pages.

    Figure-internal text (D12) overrides every type but caption. Then cover pull quotes are
    retyped body and a table of contents is typed toc.
    """
    median = body_median_size(pages)
    repeated = repeated_band_texts(pages)
    for page in pages:
        tables = _cover_tables(page, median)
        for block in page.blocks:
            block.type = _classify(block, page, median, repeated, tables)
            if block.type != "caption" and in_figure(block, page.figure_bboxes):
                block.type = "figure"
        if page.number < COVER_PAGES:
            _retype_pull_quotes(page, median)
    _mark_toc(pages, median)
    return pages
