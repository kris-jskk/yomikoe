"""Stage 2: classify blocks by type (ING-3).

Rules from docs/TECHNICAL_DESIGN.md stage 2, first match wins:
noise (off-page: less than OFF_PAGE_INSIDE_FRAC of the bbox inside the page box), noise
(rotated text), header/footer, noise (boilerplate text), heading, caption, footnote,
table, code (ING-10), equation, list, body. Then (D12) any block but a caption or a code
listing whose bbox lies at least
FIGURE_INSIDE_FRAC inside a figure region (Page.figure_bboxes) is typed figure. Two document
passes follow: cover-page pull quotes typed heading by size become body, and a table of
contents (a "Contents" heading and the TOC-like blocks after it) is typed toc (never read).
"""

from __future__ import annotations

import math
import re
import unicodedata
from collections import defaultdict
from dataclasses import replace
from itertools import pairwise
from statistics import median as _median

from hearnarro.ingestion.models import ITEM_RE, BBox, Block, BlockType, Line, Page

PAGE_NUMBER_RE = re.compile(
    r"^(?:\d+|[ivxlc]+|page\s+(?:\d+|[ivxlc]+)\b.*|\d+\s+of\s+\d+)$", re.IGNORECASE
)
# ING-4 (document 17): a block whose only text is a bracketed or bare page number ("[47]",
# "23") left mid-page by a scan-to-PDF tool or leaked from a TOC; typed noise, never read.
# A bare 19xx/20xx is kept: a lone year (a cover or title-page date) is content, not a marker.
PAGE_MARKER_RE = re.compile(r"^(?:\[\d{1,4}\]|(?!(?:19|20)\d\d$)\d{1,4})$")
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
MATH_CHARS = set("=+−-×÷∑∫√∂∞≤≥≈∝∈∀∃αβγδεθλμπσφω^_{}|")
MATH_FONT_MARKERS = ("Math", "CMSY", "CMMI", "CMEX", "CMBSY", "MSBM", "MSAM", "RSFS", "EUFM")
# ING-10 code listings (spec m5 §3d): monospace fonts, by name.
MONO_FONT_MARKERS = ("Mono", "Courier", "Consolas", "Menlo", "CMTT", "SFTT", "Inconsolata", "Code")
CODE_MONO_SHARE = 0.7  # a block this monospace by character is code
CODE_MIN_LINES = 3  # ... or this many lines, CODE_INDENTED_SHARE of them indented code lines
CODE_INDENTED_SHARE = 0.5
CODE_INDENT = 1.0  # a line is indented when it starts this many font sizes right of the block
CODE_PUNCT_RE = re.compile(r"[{};=()]|->|=>|^\s*(?:#|//)")
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
TOC_LOOKAHEAD = 3  # inside a TOC, a short block followed within this many blocks by a TOC line
TOC_NUMBER_ONLY_RE = re.compile(r"^(?:\d{1,4}|[ivxlc]+)$")  # a page-number-only entry block
TOC_SENTENCE_MIN_WORDS = 4  # a block ending in . ! ? with this many words is prose, not an entry
DROP_CAP_SIZE_RATIO = 1.5  # a single capital at least this x the body median opening a paragraph
DROP_CAP_RE = re.compile(r"^[A-Z]$")
# Cover pages: a digit-free table region with at most this many lines is a title, not a table.
COVER_TABLE_MAX_LINES = 4
EQUATION_PUNCT = set(".,;:!?")
OPENING_QUOTES = '“"‘«„'
SENTENCE_END_RE = re.compile(r"[a-z]{2,}[.!?][\"”’)]*(?=\s|$)")
PULL_QUOTE_MIN_SENTENCES = 2
# Vertical titles (found on a user book's cover: one rotated letter per line). A single
# letter (plus optional punctuation) on a cover page is noise; VSTACK_MIN or more such blocks
# on any page whose x0 lie within VSTACK_X_TOL points, stacked with no gap above
# VSTACK_SPLIT x their median height, fold into one heading read first on the page. A gap
# above VSTACK_WORD_GAP x the median letter gap is a word break.
SINGLE_LETTER_RE = re.compile(r"^[^\W\d_][.,;:!?]?$")
VSTACK_MIN = 5
VSTACK_X_TOL = 10.0
VSTACK_SPLIT = 2.0
VSTACK_WORD_GAP = 1.5
VSTACK_TYPES = {"heading", "body", "noise", "footnote", "caption", "list"}


OFF_PAGE_INSIDE_FRAC = 0.5  # a block with less of its bbox area inside the page box is noise
OFF_PAGE_KEEP_SIZE_RATIO = 1.0  # ...unless its largest span is at least this x the body median


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


def _off_page(block: Block, page: Page) -> bool:
    """Less than OFF_PAGE_INSIDE_FRAC of the block's bbox area lies inside the page box
    [0, width] x [0, height] (user decision 2026-10-16: text outside the page is never read)."""
    b = block.bbox
    box = BBox(0.0, 0.0, page.width, page.height)
    area = max(0.0, b.width) * max(0.0, b.height)
    if area <= 0:
        return not (0 <= b.x_mid <= page.width and 0 <= b.y_mid <= page.height)
    return _inter_area(b, box) < OFF_PAGE_INSIDE_FRAC * area


def _off_page_noise(block: Block, page: Page, median: float) -> bool:
    """An off-page block is noise unless its largest span is at least the body median
    (user decision 2026-10-16: keep a back-cover tagline, drop the small-print blurb)."""
    if not _off_page(block, page):
        return False
    return not (median > 0 and _max_size(block) >= OFF_PAGE_KEEP_SIZE_RATIO * median)


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


def _is_mono_font(font: str) -> bool:
    return any(m in font for m in MONO_FONT_MARKERS)


def _is_code(block: Block) -> bool:
    """A code listing (ING-10, spec m5 §3d): at least CODE_MONO_SHARE of its non-space
    characters are in a monospace font; or, with no maths font, at least CODE_MIN_LINES lines
    of which CODE_INDENTED_SHARE are indented by CODE_INDENT font sizes and hold code
    punctuation (``{ } ; = ( ) -> =>``, a leading ``#`` or ``//``)."""
    total = 0
    mono = 0
    for ln in block.lines:
        for s in ln.spans:
            n = sum(1 for ch in s.text if not ch.isspace())
            total += n
            if _is_mono_font(s.font):
                mono += n
    if total and mono >= CODE_MONO_SHARE * total:
        return True
    lines = [ln for ln in block.lines if ln.text.strip()]
    if len(lines) < CODE_MIN_LINES:
        return False
    if any(_is_math_font(s.font) for ln in lines for s in ln.spans):
        return False
    indent = CODE_INDENT * max(_max_size(block), 1.0)
    coded = sum(
        1 for ln in lines if ln.bbox.x0 - block.bbox.x0 >= indent and CODE_PUNCT_RE.search(ln.text)
    )
    return coded >= CODE_INDENTED_SHARE * len(lines)


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


def _lone_letter(block: Block, page: Page) -> bool:
    """A single rotated letter in a text font with no other block on its text row within three
    of its heights (an upright drop cap or a maths letter in a cover-page formula is not one)."""
    if not SINGLE_LETTER_RE.match(" ".join(block.text.split())):
        return False
    if any(ln.dir == (1.0, 0.0) for ln in block.lines):
        return False  # upright: a drop cap or a maths letter, not a rotated title letter
    if any(_is_math_font(s.font) for ln in block.lines for s in ln.spans):
        return False
    reach = 3 * block.bbox.height
    return not any(
        o is not block
        and o.bbox.y0 < block.bbox.y1
        and block.bbox.y0 < o.bbox.y1
        and o.bbox.x0 - reach < block.bbox.x1
        and block.bbox.x0 < o.bbox.x1 + reach
        for o in page.blocks
    )


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
    if page.number < COVER_PAGES and _lone_letter(block, page):
        return True  # one letter of a vertical cover title
    tokens = " ".join(lines).split()
    if len(tokens) >= 6 and all(len(t) == 1 and t.isalpha() for t in tokens):
        return True  # letter-spaced banner, e.g. "C O M P U T E R   S E C U R I T Y"
    return (
        page.number < COVER_PAGES
        and block.bbox.y0 >= SIGNATURE_TOP_FRAC * page.height
        and SIGNATURE_RE.search(" ".join(lines)) is not None
    )


# MATH-1, ING-3 (m5 p3h): a display set in a text font (textbook pages: "p + q = 1",
# "n − 1 or s = Σ f(x − x̄)") has no maths font for _is_equation. A short body block standing
# alone on its line (no body, list, heading or caption block shares it) whose text, a trailing "(N)" label aside, is
# maths by content (merge.content_spans, maths-font or MATH_CHARS glyphs) for at least
# TEXT_DISPLAY_SHARE of its characters, holds a relation or an operation and at most
# TEXT_DISPLAY_WORDS prose words is a display equation.
TEXT_DISPLAY_SHARE = 0.6
TEXT_DISPLAY_WORDS = 1
TEXT_DISPLAY_MAX_CHARS = 80
TEXT_DISPLAY_MAX_LINES = 3
TEXT_DISPLAY_OPS = set("=<>≤≥∼~≈≡∝→∈−+±×÷·Σ∑∫√")
_LABEL_TAIL_RE = re.compile(r"\s*\(\d{1,3}[a-z]?\)\s*$")
_PROSE_WORD_RE = re.compile(r"[A-Za-z]{3,}")


def _text_display(block: Block) -> bool:
    from hearnarro.ingestion.merge import _FUNCTION_RE, content_spans

    lines = [ln for ln in block.lines if ln.text.strip()]
    if not lines or len(lines) > TEXT_DISPLAY_MAX_LINES:
        return False
    text = _LABEL_TAIL_RE.sub("", " ".join(ln.text.strip() for ln in lines))
    total = sum(1 for c in text if not c.isspace())
    if not 3 <= total <= TEXT_DISPLAY_MAX_CHARS or not any(c in TEXT_DISPLAY_OPS for c in text):
        return False
    if len(_PROSE_WORD_RE.findall(_FUNCTION_RE.sub("", text))) > TEXT_DISPLAY_WORDS:
        return False
    covered = [False] * len(text)
    for sp in content_spans(text):
        covered[sp.start : sp.end] = [True] * (sp.end - sp.start)
    glyphs = {c for ln in lines for s in ln.spans if _is_math_font(s.font) for c in s.text}
    maths = sum(
        1
        for k, c in enumerate(text)
        if not c.isspace() and (covered[k] or c in MATH_CHARS or c in glyphs)
    )
    return maths >= TEXT_DISPLAY_SHARE * total


def _retype_text_displays(page: Page) -> None:
    """Body blocks that are text-font displays (``_text_display``) alone on their line become
    equation blocks; stage 3 then joins their pieces (order.merge_display_pieces)."""
    # Any text block on the line, short or long, means the maths is part of a sentence or of
    # a list item (formula_06's "• s = Σ(x − x̄)" row), not a display of its own (gate (e):
    # retyping those moves glyph tokens out of the prose the profile measures).
    prose = [b for b in page.blocks if b.type in ("body", "list", "heading", "caption")]
    for block in page.blocks:
        if block.type != "body" or not _text_display(block):
            continue
        if any(
            p is not block
            and min(p.bbox.y1, block.bbox.y1) - max(p.bbox.y0, block.bbox.y0) > 0
            and any(
                min(ln.bbox.y1, block.bbox.y1) - max(ln.bbox.y0, block.bbox.y0) > 0
                for ln in p.lines
            )
            for p in prose
        ):
            continue
        block.type = "equation"


def _classify(
    block: Block, page: Page, median: float, repeated: set[str], tables: list[BBox]
) -> BlockType:
    text = block.text.strip()
    if _off_page_noise(block, page, median):
        return "noise"
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
    if PAGE_MARKER_RE.match(text) and not any(block.bbox.overlaps(t) for t in tables):
        return "noise"  # ING-4: a page marker outside the TOC region (and outside any table)
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
    if _is_code(block):
        return "code"
    if _is_equation(block):
        return "equation"
    if ITEM_RE.match(block.lines[0].text):
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
    if len(lines) == 1 and (_is_leader_line(lines[0]) or TOC_NUMBER_ONLY_RE.match(lines[0])):
        return True
    hits = sum(
        1
        for ln in lines
        if _is_leader_line(ln)
        or TOC_PAGE_NUMBER_RE.search(ln)
        or len(TOC_INNER_NUMBER_RE.findall(ln)) >= 2
    )
    return hits >= TOC_LINE_SHARE * len(lines)


def _is_sentence(block: Block) -> bool:
    text = " ".join(block.text.split())
    return len(text.split()) >= TOC_SENTENCE_MIN_WORDS and text.rstrip('"”’)').endswith(
        (".", "!", "?")
    )


def _mark_toc(pages: list[Page], median: float) -> None:
    """A block of any type reading "Contents" or "Table of contents" opens a TOC region; it
    runs over the TOC-like blocks after it (a page-number-only block counts), across pages, and
    ends at the first other block once one TOC-like block was seen, at a body-size-or-larger
    heading, at a sentence, or after TOC_MAX_PAGES pages. Short blocks before the first TOC-like
    one join it, and so do short ones after it that a TOC-like block follows within
    TOC_LOOKAHEAD blocks (an entry title above its page number). A region with no TOC-like block
    types nothing (ING-3).
    """
    flow = [
        (page.number, block)
        for page in pages
        for block in page.blocks
        if block.type not in ("header", "footer", "figure", "image") and block.text.strip()
    ]
    region: list[Block] = []
    seen = False
    start = 0

    def close() -> None:
        nonlocal region, seen
        if seen:
            for b in region:
                b.type = "toc"
        region, seen = [], False

    def entry_title(i: int) -> bool:
        for _, later in flow[i + 1 : i + 1 + TOC_LOOKAHEAD]:
            if _is_sentence(later) or len(later.lines) > TOC_LEAD_MAX_LINES:
                return False
            if _toc_like(later):
                return True
        return False

    for i, (number, block) in enumerate(flow):
        if region and number - start >= TOC_MAX_PAGES:
            close()
        if region:
            lines = [ln for ln in block.lines if ln.text.strip()]
            if _toc_like(block):
                region.append(block)
                seen = True
                continue
            big_heading = block.type == "heading" and _max_size(block) >= median
            short = len(lines) <= TOC_LEAD_MAX_LINES and not big_heading
            if short and (not seen or (not _is_sentence(block) and entry_title(i))):
                region.append(block)
                continue
            close()
        if TOC_HEADING_RE.match(normalize_key(block.text)):
            region, seen, start = [block], False, number
    close()


def _join_drop_caps(page: Page, median: float) -> None:
    """A single capital letter at least DROP_CAP_SIZE_RATIO x the body median (a drop cap)
    joins the body block whose first line starts inside its vertical extent, to its right,
    with a lowercase letter: the letter is prepended and the cap typed noise (ING-3)."""
    for cap in page.blocks:
        if cap.type not in ("heading", "body") or not DROP_CAP_RE.match(cap.text.strip()):
            continue
        if _max_size(cap) < DROP_CAP_SIZE_RATIO * median:
            continue
        paras = [
            b
            for b in page.blocks
            if b is not cap
            and b.type == "body"
            and b.lines
            and cap.bbox.y0 <= b.lines[0].bbox.y0 < cap.bbox.y1
            and b.lines[0].bbox.x0 >= cap.bbox.x0 - 1.0
            and b.text[:1].islower()
        ]
        if not paras:
            continue
        para = min(paras, key=lambda b: (b.lines[0].bbox.y0, b.lines[0].bbox.x0))
        first = para.lines[0]
        first.spans[0] = replace(first.spans[0], text=cap.text.strip() + first.spans[0].text)
        cap.type = "noise"


def _fold_stack(run: list[Block]) -> None:
    """Turn the first block of a vertical letter run into the whole title; the rest is noise."""
    gaps = [b.bbox.y0 - a.bbox.y1 for a, b in pairwise(run)]
    word_gap = VSTACK_WORD_GAP * max(_median(gaps), 0.1)
    text = run[0].text.strip()
    for gap, b in zip(gaps, run[1:], strict=False):
        text += (" " if gap > word_gap else "") + b.text.strip()
    spans = [s for b in run for ln in b.lines for s in ln.spans]
    box = BBox(
        min(b.bbox.x0 for b in run),
        min(b.bbox.y0 for b in run),
        max(b.bbox.x1 for b in run),
        max(b.bbox.y1 for b in run),
    )
    head = max(spans, key=lambda s: s.size)
    title = run[0]
    title.lines = [Line(spans=[replace(head, text=text, bbox=box)], bbox=box)]
    title.bbox = box
    title.type = "heading"
    title.lead = True
    for b in run[1:]:
        b.type = "noise"


def _fold_vertical_titles(page: Page) -> None:
    """Fold stacks of single-letter blocks (a vertical title) into one heading each."""
    cands = [
        b
        for b in page.blocks
        if b.type in VSTACK_TYPES and SINGLE_LETTER_RE.match(" ".join(b.text.split()))
    ]
    if len(cands) < VSTACK_MIN:
        return
    clusters: list[list[Block]] = []
    for b in sorted(cands, key=lambda b: b.bbox.x0):
        if clusters and b.bbox.x0 - clusters[-1][0].bbox.x0 <= VSTACK_X_TOL:
            clusters[-1].append(b)
        else:
            clusters.append([b])
    for cluster in clusters:
        cluster.sort(key=lambda b: b.bbox.y0)
        split = VSTACK_SPLIT * _median(b.bbox.height for b in cluster)
        runs: list[list[Block]] = [[cluster[0]]]
        for a, b in pairwise(cluster):
            if b.bbox.y0 - a.bbox.y1 > split:
                runs.append([b])
            else:
                runs[-1].append(b)
        for run in runs:
            if len(run) >= VSTACK_MIN:
                _fold_stack(run)


def classify_pages(pages: list[Page]) -> list[Page]:
    """Set block.type in place (first matching rule wins) and return pages.

    Figure-internal text (D12) overrides every type but caption and code (ING-10: a listing
    on a shaded box is still read as its cue). Then cover pull quotes are
    retyped body, vertical letter stacks fold into one heading, drop caps join their
    paragraph, and a table of contents is typed toc.
    """
    median = body_median_size(pages)
    repeated = repeated_band_texts(pages)
    for page in pages:
        tables = _cover_tables(page, median)
        for block in page.blocks:
            block.type = _classify(block, page, median, repeated, tables)
            if block.type not in ("caption", "code") and in_figure(block, page.figure_bboxes):
                block.type = "figure"
        _retype_text_displays(page)
        if page.number < COVER_PAGES:
            _retype_pull_quotes(page, median)
        _fold_vertical_titles(page)
        _join_drop_caps(page, median)
    _mark_toc(pages, median)
    for page in pages:  # off-page small print stays noise whatever the document passes did
        for block in page.blocks:
            if _off_page_noise(block, page, median):
                block.type = "noise"
    return pages
