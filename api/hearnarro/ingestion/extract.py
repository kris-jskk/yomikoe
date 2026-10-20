"""Stage 1: extract spans from a PDF, OCR pages without a text layer (D1, D13, ING-2).

Text, fonts, drawings, images and tables come from pdfplumber (MIT; pdfminer.six underneath);
page rendering for OCR comes from pypdfium2 (Apache-2.0/BSD-3). D13 replaced PyMuPDF (AGPL).
"""

from __future__ import annotations

import importlib.util
import itertools
import re
import shutil
import struct
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from statistics import median
from typing import Any

import pdfplumber

from hearnarro.ingestion.models import BBox, Block, Line, Page, Span
from hearnarro.ingestion.ocr import DEFAULT_OCR, OCRBackend, _Default

OCR_DPI = 300
FIGURE_MIN_FRAC = 0.02  # a drawings union covering less of the page is a rule or a box
FIGURE_MAX_FRAC = 0.80  # ... and one covering this much or more is a page background
# pdfplumber reports each box, arrow and curve of a vector figure separately; a curve joins
# drawings within FIGURE_JOIN points of it (tuned 2026-10-16 on pdfplumber; padding plain
# rects too merges the shaded rows of report text boxes into "figures", results 139).
FIGURE_JOIN = 6.0
# Glyph grouping (D13). pdfminer's own layout analysis (LAParams) splits justified lines at
# wide word gaps and splits inline math into separate boxes, so stage 1 groups pdfplumber's
# glyphs itself, in content-stream order, the way PyMuPDF's text device did: a glyph continues
# the current line when it overlaps it vertically and does not jump backwards; a line joins
# the current block when it overlaps the block, or sits within BLOCK_GAP sizes below it at a
# compatible font size.
BASELINE_JUMP: float | None = 0.8
SPACE_NEXT_SIZE = True  # measure the gap in the next glyph's size, as MuPDF does
SPACE_GAP = 0.15  # a gap wider than this many font sizes between glyphs is a word space
LINE_OVERLAP = 0.3  # min vertical overlap (fraction of the smaller height) to stay on a line
LINE_BACKSTEP = 0.5  # a glyph starting this many sizes left of the previous one ends the line
OVERSTRIKE = True  # see _continues_line
LINE_MAX_GAP = 10.0  # ... as does a forward jump wider than this many sizes
# Tracked (letter-spaced) text, found on a user book's cover and dedication: a line of at least
# TRACKED_MIN_TOKENS tokens, TRACKED_SHARE of them single letters, keeps a word break only at
# gaps of TRACKED_WORD_GAP x the median gap between its fragments (see retrack).
TRACKED_MIN_TOKENS: int | None = 6
TRACKED_SHARE = 0.7
TRACKED_WORD_GAP = 2.0
BLOCK_GAP = 0.5  # max vertical gap between a block and its next line, in font sizes
BLOCK_SIZE_RATIO = 1.25  # max ratio between line font sizes inside one block
# MuPDF's text-indent paragraph rule (D13), applied to tagged PDFs only (glyphs carry
# marked-content ids; Word/Acrobat output): a line starting INDENT_NEW_BLOCK points right of
# the previous line's start opens a new block (a first-line-indented paragraph, or the next
# ragged-left cover line); measured in results 130.
INDENT_NEW_BLOCK: float | None = 0.5
# In untagged PDFs only a small move (<= UNTAGGED_INDENT_MAX points: the line before hung into
# the margin, e.g. an opening "(" or "W" set by microtype) opens a block; larger moves are
# hanging indents of list items and wrapped headings.
UNTAGGED_INDENT_MAX: float | None = 2.0
# ... and so does a centred line under a wider centred line (title, author list), and the
# hanging-indented continuation of a numbered reference entry ("[12] A. Author, ...").
CENTRE_TOL: float | None = 3.0
CENTRE_INDENT = 5.0
_REF_ENTRY = re.compile(r"^\[\d+\]")
# MuPDF's "way off the baseline" paragraph rule: a line whose baseline sits more than
# PARA_BASELINE font sizes below the previous line's opens a new block, even when tall glyphs
# (display-equation delimiters, stacked limits) make the boxes touch.
PARA_BASELINE: float | None = 1.6
MAX_DESCENT = 0.8  # glyph boxes of a font whose descent exceeds this (in sizes) are lifted ...
NORMAL_DESCENT = 0.25  # ... to this descent (TeX text fonts)
RULE_MAX_HEIGHT = 1.5  # a table rule is at most this thick ...
RULE_MIN_WIDTH = 50.0  # ... and at least this wide (points)
RULE_ALIGN = 3.0  # rules of one table start and end within this many points of each other
RULE_STACK_GAP = 0.5  # ... and lie within this fraction of the page height of the next
RULE_STACK_MIN = 3  # top rule, mid rule, bottom rule
COLUMN_ROWS = 2  # ... on at least this many lines
COLUMN_GAP = 1.0  # a glyph gap this many font sizes wide inside a ruled region is a column gap
# Prose in a frame is no table (ING-3, ING-4; m5 p3d, formula_08/09): a table region holding more
# than TABLE_PROSE_LINES_MAX lines of running prose (no column gap, at least PROSE_LINE_WIDTH of
# the region wide) is prose between rules (M1 tables: at most 2); a find_tables region at least
# TEXTBOX_MIN_WIDTH of the page wide with no column gap on any line is a framed text box (an
# exercise or admonition box with a title row), so neither a table nor, where a drawn figure
# region coincides with it (TEXTBOX_COVER of the figure's area), a figure.
TABLE_PROSE_LINES_MAX = 3
PROSE_LINE_WIDTH = 0.6
TEXTBOX_MIN_WIDTH = 0.6
TEXTBOX_COVER = 0.9
# Display-equation lines (ING-3): a line holding a math-font glyph whose text-font letters are
# under MATH_LINE_PROSE of its glyphs is "math"; a block never mixes math and prose lines.
MATH_FONT_MARKERS = ("Math", "CMSY", "CMMI", "CMEX", "CMBSY", "MSBM", "MSAM", "RSFS", "EUFM")
MATH_LINE_PROSE: float | None = 0.3
SCRIPT_RATIO = 0.8  # a glyph this much smaller than its line's dominant size is a script
SUPERSCRIPT_SIZE_RATIO = 0.75  # a char this much smaller than the line's dominant size ...
SUPERSCRIPT_RAISE = 0.2  # ... whose bottom sits this many dominant sizes higher is raised

# TeX symbol glyphs MuPDF set without a following word space (D13 parity with the D11/D12
# ground truth, measured in results 131): CMSY/CMR relations, arrows, minus and ∆, and spacing
# accents in any font ("B¨ uhlmann"). "|", "×", "·", "′", "†", "Π", "Θ" keep their space.
_TIGHT_FONT = re.compile(r"^CM(?:SY|R)\d")
_TIGHT_SYMBOLS = frozenset("∈∉≤≥∼≈≃≡∝−→←↔⇒∥⊤⊥⊂⊆⊃⊇∆∗≫≪≲≳⊗⊕∞7")
_SPACING_ACCENTS = frozenset("¨ˆ˜´`¯˙˘ˇ˚")
_SUBSET_PREFIX = re.compile(r"^[A-Z]{6}\+")
_CID = re.compile(r"\(cid:(\d+)\)")
_BOLD_RE = re.compile(r"bold|black|heavy|semibold|demi|medi|cmbx", re.IGNORECASE)
_ITALIC_RE = re.compile(r"italic|ital|oblique|cmti", re.IGNORECASE)


class OCRUnavailable(RuntimeError):
    """Raised when OCR is required but pytesseract or the tesseract binary is missing."""


def ocr_available() -> bool:
    """True when pytesseract is importable AND the tesseract binary is on PATH."""
    try:
        has_module = importlib.util.find_spec("pytesseract") is not None
    except (ImportError, ValueError):
        has_module = False
    return has_module and shutil.which("tesseract") is not None


@dataclass(frozen=True)
class LayoutChar:
    """One glyph from any extractor, in top-left page coordinates.

    ``bbox`` is None for a virtual space the extractor inserted between words; it joins the
    surrounding span's text and carries no geometry.
    """

    text: str
    bbox: BBox | None
    font: str = ""
    size: float = 0.0
    upright: bool = True
    mcid: int | None = None  # marked-content id (tagged PDFs)


LayoutLine = Sequence[LayoutChar]
LayoutBox = Sequence[LayoutLine]


def font_flags(font: str) -> tuple[bool, bool]:
    """(bold, italic) from a font name: "Bold"/",B"/"-B" (and Black, Heavy, Semibold, Medium, CMBX)
    mean bold; "Italic"/"Oblique" (and CMTI) mean italic."""
    bold = bool(_BOLD_RE.search(font)) or font.endswith((",B", "-B", ",BoldItalic"))
    italic = bool(_ITALIC_RE.search(font)) or font.endswith((",I", "-I", "-It"))
    return bold, italic


def _union(boxes: Sequence[BBox]) -> BBox:
    return BBox(
        min(b.x0 for b in boxes),
        min(b.y0 for b in boxes),
        max(b.x1 for b in boxes),
        max(b.y1 for b in boxes),
    )


def _line_from_layout(chars: LayoutLine) -> Line | None:
    """Group consecutive glyphs with the same (font, size, upright, superscript) into Spans."""
    glyphs = [c for c in chars if c.bbox is not None and c.text]
    if not glyphs:
        return None
    sizes = Counter(round(c.size, 1) for c in glyphs)
    dominant = max(sizes, key=lambda s: (sizes[s], s))
    bottoms = [c.bbox.y1 for c in glyphs if round(c.size, 1) == dominant and c.bbox]
    base = median(bottoms)

    def raised(c: LayoutChar) -> bool:
        assert c.bbox is not None
        return (
            c.size <= SUPERSCRIPT_SIZE_RATIO * dominant
            and base - c.bbox.y1 > SUPERSCRIPT_RAISE * dominant
        )

    upright = all(c.upright for c in glyphs)
    spans: list[Span] = []
    key: tuple[str, float, bool, bool] | None = None
    text: list[str] = []
    boxes: list[BBox] = []

    def flush() -> None:
        if key is None or not boxes:
            return
        font, size, _upright, sup = key
        bold, italic = font_flags(font)
        spans.append(
            Span(
                text="".join(text),
                bbox=_union(boxes),
                font=font,
                size=size,
                bold=bold,
                italic=italic,
                superscript=sup,
            )
        )

    for c in chars:
        if c.bbox is None:  # virtual space: belongs to the current span
            if key is not None:
                text.append(c.text)
            continue
        letters = c.text.translate(LIGATURE_CHARS)  # ING-5: "\ufb01" -> "fi"
        if upright:
            k = (c.font, round(c.size, 2), True, raised(c))
        else:  # pdfminer reports a rotated glyph's advance as its size; use the line's
            k = (c.font, dominant, False, False)
        if k == key and upright and boxes and _level_jump(boxes[-1], c.bbox, c.size):
            flush()  # one font on two levels of a display (numerator, row): two spans (m5 p3n)
            text, boxes = [], []
        if k != key:
            flush()
            key, text, boxes = k, [], []
        text.append(letters)
        boxes.append(c.bbox)
    flush()
    spans = [s for s in spans if s.text]
    if not spans:
        return None
    if spans[-1].text.endswith("\n"):
        spans[-1].text = spans[-1].text.rstrip("\n")
    return Line(
        spans=spans,
        bbox=_union([s.bbox for s in spans]),
        dir=(1.0, 0.0) if upright else (0.0, 1.0),
    )


LEVEL_JUMP = 0.5  # a glyph whose top and bottom both move this many sizes is on another level


def _level_jump(prev: BBox, box: BBox, size: float) -> bool:
    """``box`` sits on another vertical level than ``prev`` (a display's numerator after its
    main row): the span is split so structure.py sees each level's geometry (MATH-1, m5 p3n)."""
    tol = LEVEL_JUMP * max(size, 1.0)
    return abs(box.y0 - prev.y0) > tol and abs(box.y1 - prev.y1) > tol


def page_from_layout(
    number: int,
    width: float,
    height: float,
    text_boxes: Sequence[LayoutBox],
    image_bboxes: Sequence[BBox] = (),
    table_bboxes: Sequence[BBox] = (),
) -> Page:
    """Build a Page from extractor-agnostic layout boxes (pure).

    ``text_boxes`` is a list of boxes, each a list of lines, each a list of LayoutChar.
    Block.index is the box's position in ``text_boxes``; boxes with no text are skipped.
    """
    blocks: list[Block] = []
    for index, box in enumerate(text_boxes):
        lines = [ln for ln in (_line_from_layout(chars) for chars in box) if ln is not None]
        lines = [ln for ln in lines if ln.text.strip()]
        if not lines:
            continue
        bbox = _union([ln.bbox for ln in lines])
        blocks.append(Block(page=number, index=index, bbox=bbox, lines=lines))
    page = Page(
        number=number,
        width=width,
        height=height,
        blocks=blocks,
        image_bboxes=list(image_bboxes),
        table_bboxes=list(table_bboxes),
    )
    page.text_chars = _char_count(page)
    return page


def _char_count(page: Page) -> int:
    """Non-space glyphs on the page (ING-2 ``Page.text_chars``)."""
    return sum(
        1
        for b in page.blocks
        for ln in b.lines
        for s in ln.spans
        for c in s.text
        if not c.isspace()
    )


def _touch(a: BBox, b: BBox) -> bool:
    """Boxes overlap or share an edge."""
    return a.x0 <= b.x1 and b.x0 <= a.x1 and a.y0 <= b.y1 and b.y0 <= a.y1


def _area(b: BBox) -> float:
    return max(0.0, b.width) * max(0.0, b.height)


def figure_regions(
    image_bboxes: Sequence[BBox],
    drawing_rects: Sequence[BBox],
    page_width: float,
    page_height: float,
) -> list[BBox]:
    """Figure regions of a page (D12, ING-3): every image bbox, plus the bbox of each
    transitive union of touching/overlapping drawing rects whose area is in
    [FIGURE_MIN_FRAC, FIGURE_MAX_FRAC) of the page area."""
    clusters: list[BBox] = []
    for rect in drawing_rects:
        if rect.height <= RULE_MAX_HEIGHT and rect.width >= RULE_MIN_WIDTH:
            continue  # a table rule or separator, never a figure part on its own
        cur = rect
        merged = True
        while merged:
            merged = False
            keep: list[BBox] = []
            for c in clusters:
                if _touch(c, cur):
                    cur = _union([c, cur])
                    merged = True
                else:
                    keep.append(c)
            clusters = keep
        clusters.append(cur)
    page_area = page_width * page_height
    drawn = [
        c for c in clusters if FIGURE_MIN_FRAC * page_area <= _area(c) < FIGURE_MAX_FRAC * page_area
    ]
    return [*image_bboxes, *drawn]


class _Coords:
    """pdfminer (origin bottom-left, MediaBox-relative) -> page top-left, as pdfplumber does."""

    def __init__(self, page: Any) -> None:
        self.height = float(page.height)
        self.mb_x0 = float(page.mediabox[0])
        self.mb_top = float(page.mediabox[1])
        self.ox = float(page.bbox[0])
        self.oy = float(page.bbox[1])

    def lt(self, x0: float, y0: float, x1: float, y1: float) -> BBox:
        top = self.height - y1 + self.mb_top - self.oy
        bottom = self.height - y0 + self.mb_top - self.oy
        return BBox(x0 + self.mb_x0 - self.ox, top, x1 + self.mb_x0 - self.ox, bottom)

    def obj(self, o: dict[str, Any]) -> BBox:
        """A pdfplumber object/bbox already in (x0, top, x1, bottom)."""
        return BBox(
            float(o["x0"]) - self.ox,
            float(o["top"]) - self.oy,
            float(o["x1"]) - self.ox,
            float(o["bottom"]) - self.oy,
        )


def _vspan(c: LayoutChar) -> tuple[float, float]:
    """Extent across the reading direction: y for upright glyphs, x for rotated ones."""
    assert c.bbox is not None
    return (c.bbox.y0, c.bbox.y1) if c.upright else (c.bbox.x0, c.bbox.x1)


def _hspan(c: LayoutChar) -> tuple[float, float]:
    """Extent along the reading direction (rotated text is read bottom to top)."""
    assert c.bbox is not None
    return (c.bbox.x0, c.bbox.x1) if c.upright else (-c.bbox.y1, -c.bbox.y0)


def _continues_line(prev: LayoutChar, line_v: tuple[float, float], c: LayoutChar) -> bool:
    if c.upright != prev.upright:
        return False
    v0, v1 = _vspan(c)
    overlap = min(v1, line_v[1]) - max(v0, line_v[0])
    accent = _is_accent(c) or _is_accent(prev)
    if not accent and overlap < LINE_OVERLAP * min(v1 - v0, line_v[1] - line_v[0]):
        return False  # an accent sits above its letter; only the horizontal test applies
    size = max(c.size, prev.size, 1.0)
    gap = _hspan(c)[0] - _hspan(prev)[1]
    if gap < -LINE_BACKSTEP * size and OVERSTRIKE:
        # an overstrike (an accent then its letter, "/" over "∈") steps back onto the
        # previous glyph: it continues the line when it starts no earlier than that glyph
        return _hspan(c)[0] >= _hspan(prev)[0] - LINE_BACKSTEP * size
    return -LINE_BACKSTEP * size <= gap <= LINE_MAX_GAP * size


def _baseline_jump(prev: LayoutChar, c: LayoutChar) -> bool:
    """MuPDF starts a new line (read with a space) when the baseline moves more than
    BASELINE_JUMP of the next glyph's size: stacked sub/superscripts, limits, radicals."""
    if BASELINE_JUMP is None or not (c.upright and prev.upright) or _is_accent(prev):
        return False
    assert c.bbox is not None and prev.bbox is not None
    jump = (c.bbox.y1 - NORMAL_DESCENT * c.size) - (prev.bbox.y1 - NORMAL_DESCENT * prev.size)
    return abs(jump) > BASELINE_JUMP * max(c.size, 1.0)


def _tight_after(c: LayoutChar) -> bool:
    """No word space is inserted after this glyph (see _TIGHT_FONT)."""
    if _is_accent(c):
        return True
    return bool(_TIGHT_FONT.match(c.font)) and c.text in _TIGHT_SYMBOLS


def _tokens(line: Sequence[LayoutChar]) -> list[list[LayoutChar]]:
    """Runs of real glyphs between virtual spaces."""
    out: list[list[LayoutChar]] = [[]]
    for c in line:
        if c.bbox is None:
            if out[-1]:
                out.append([])
        else:
            out[-1].append(c)
    return [t for t in out if t]


def _is_fragment(tok: Sequence[LayoutChar]) -> bool:
    """A piece of tracked text: one glyph, or a kerned pair of capitals ("OT", "AY")."""
    text = "".join(c.text for c in tok)
    return len(text) == 1 or (len(text) == 2 and text.isalpha() and text.isupper())


def retrack(line: list[LayoutChar]) -> list[LayoutChar]:
    """Re-split a letter-spaced (tracked) line: "F O R M Y" -> "FOR MY".

    Applies when the line has at least TRACKED_MIN_TOKENS tokens, TRACKED_SHARE of them single
    letters but not all (a pure banner such as "C O M P U T E R" stays for stage 2's noise
    rule), and no maths-font glyph. Tracking puts every glyph gap above SPACE_GAP, so each
    gets a virtual space; a space between two tracked fragments is kept only when its gap is
    at least TRACKED_WORD_GAP x the median of such gaps. Other spaces are untouched.
    """
    if TRACKED_MIN_TOKENS is None or not line or not line[0].upright:
        return line
    toks = _tokens(line)
    single = sum(1 for t in toks if len(t) == 1 and t[0].text.isalpha())
    if len(toks) < TRACKED_MIN_TOKENS or single < TRACKED_SHARE * len(toks):
        return line
    if single == len(toks) or any(is_math_font(c.font) for t in toks for c in t):
        return line  # a pure letter-spaced banner stays as it is (stage 2 types it noise)
    pairs = [
        (_hspan(b[0])[0] - _hspan(a[-1])[1], a, b)
        for a, b in itertools.pairwise(toks)
        if _is_fragment(a) and _is_fragment(b)
    ]
    if not pairs:
        return line
    limit = TRACKED_WORD_GAP * median(g for g, _, _ in pairs)
    joined = {id(b) for g, _, b in pairs if g < limit}
    out: list[LayoutChar] = []
    for i, t in enumerate(toks):
        if i and id(t) not in joined:
            out.append(LayoutChar(" ", None))
        out.extend(t)
    return out


def group_lines(chars: Sequence[LayoutChar]) -> list[list[LayoutChar]]:
    """Split glyphs (content-stream order, real glyphs only) into lines, inserting virtual
    spaces at word gaps. Pure."""
    lines: list[list[LayoutChar]] = []
    line_v = (0.0, 0.0)
    prev: LayoutChar | None = None
    for c in chars:
        if c.bbox is None:
            continue
        if not c.text.strip():  # a real space glyph: keep it as a virtual space
            if prev is not None and lines and lines[-1][-1].bbox is not None:
                lines[-1].append(LayoutChar(" ", None))
            continue
        if prev is not None and _continues_line(prev, line_v, c):
            gap = _hspan(c)[0] - _hspan(prev)[1]
            if (
                (
                    gap > SPACE_GAP * (c.size if SPACE_NEXT_SIZE else max(c.size, prev.size))
                    or _baseline_jump(prev, c)
                )
                and lines[-1][-1].bbox is not None
                and not _tight_after(prev)
            ):
                lines[-1].append(LayoutChar(" ", None))
            lines[-1].append(c)
            if not _is_accent(c):
                v0, v1 = _vspan(c)
                line_v = (min(line_v[0], v0), max(line_v[1], v1))
        else:
            lines.append([c])
            line_v = _vspan(c)
        prev = c
    for ln in lines:
        while ln and ln[-1].bbox is None:
            ln.pop()
    return [retrack(ln) for ln in lines if ln]


def _line_metrics(line: list[LayoutChar]) -> tuple[BBox, float, bool]:
    glyphs = [c for c in line if c.bbox is not None]
    sizes = Counter(round(c.size, 1) for c in glyphs)
    size = max(sizes, key=lambda s: (sizes[s], s))
    return _union([c.bbox for c in glyphs if c.bbox is not None]), size, glyphs[0].upright


def group_blocks(lines: Sequence[list[LayoutChar]]) -> list[list[list[LayoutChar]]]:
    """Group lines (stream order) into blocks. Pure."""
    blocks: list[list[list[LayoutChar]]] = []
    cur_box: BBox | None = None
    cur_size = 0.0
    cur_upright = True
    prev_box: BBox | None = None
    prev_line: list[LayoutChar] = []
    for line in lines:
        box, size, upright = _line_metrics(line)
        join = False
        if cur_box is not None and upright == cur_upright:
            if (
                MATH_LINE_PROSE is not None
                and prev_box is not None
                and min(box.y1, prev_box.y1) <= max(box.y0, prev_box.y0)  # a new text row
                and is_math_line(line) != is_math_line(prev_line)
            ) or (
                upright
                and PARA_BASELINE is not None
                and prev_line
                and _baseline(line) - _baseline(prev_line) > PARA_BASELINE * size
            ):
                join = False
            elif box.overlaps(cur_box):
                join = True
            elif (
                upright
                and INDENT_NEW_BLOCK is not None
                and prev_box is not None
                and box.y0 >= prev_box.y1 - 0.5 * size
                and box.x0 > prev_box.x0 + INDENT_NEW_BLOCK
                and (
                    _tagged(prev_line, line)
                    or (
                        UNTAGGED_INDENT_MAX is not None
                        and box.x0 <= prev_box.x0 + UNTAGGED_INDENT_MAX
                    )
                    or _centred_pair(prev_box, box)
                    or _REF_ENTRY.match(_text(prev_line)) is not None
                )
            ):
                join = False
            else:
                ratio = max(size, cur_size) / max(min(size, cur_size), 0.1)
                if upright:
                    gap = box.y0 - cur_box.y1
                    across = min(box.x1, cur_box.x1) - max(box.x0, cur_box.x0)
                else:
                    gap = box.x0 - cur_box.x1
                    across = min(box.y1, cur_box.y1) - max(box.y0, cur_box.y0)
                join = (
                    ratio <= BLOCK_SIZE_RATIO
                    and -0.5 * size <= gap <= BLOCK_GAP * max(size, cur_size)
                    and across > 0
                )
        if join and cur_box is not None:
            blocks[-1].append(line)
            cur_box = _union([cur_box, box])
            cur_size = max(cur_size, size) if box.overlaps(cur_box) else size
        else:
            blocks.append([line])
            cur_box, cur_size, cur_upright = box, size, upright
        prev_box, prev_line = box, line
    return blocks


def is_math_line(line: Sequence[LayoutChar]) -> bool:
    """A display-maths line: it holds a math-font glyph and its prose letters (letters in
    text fonts at no less than SCRIPT_RATIO of the line's dominant size; smaller ones are
    sub/superscripts such as operator names) are under MATH_LINE_PROSE of its glyphs."""
    glyphs = [c for c in line if c.bbox is not None and c.text.strip()]
    if not glyphs or MATH_LINE_PROSE is None:
        return False
    if not any(is_math_font(c.font) for c in glyphs):
        return False
    sizes = Counter(round(c.size, 1) for c in glyphs)
    dominant = max(sizes, key=lambda s: (sizes[s], s))
    prose = sum(
        1
        for c in glyphs
        if c.text.isalpha() and not is_math_font(c.font) and c.size >= SCRIPT_RATIO * dominant
    )
    return prose < MATH_LINE_PROSE * len(glyphs)


def is_math_font(font: str) -> bool:
    """A TeX/Unicode maths font (MATH_FONT_MARKERS)."""
    return any(m in font for m in MATH_FONT_MARKERS)


def _is_accent(c: LayoutChar) -> bool:
    """A spacing accent, or a CMEX wide hat/tilde (pdfminer maps those to "b".."g")."""
    return c.text in _SPACING_ACCENTS or (c.font.startswith("CMEX") and c.text in "bcdefg")


def _text(line: Sequence[LayoutChar]) -> str:
    return "".join(c.text for c in line).strip()


def _centred_pair(prev: BBox, box: BBox) -> bool:
    """Two centred lines (a title, an author list): same centre within CENTRE_TOL points,
    the second at least CENTRE_INDENT points narrower on the left."""
    return (
        CENTRE_TOL is not None
        and abs(box.x_mid - prev.x_mid) <= CENTRE_TOL
        and box.x0 - prev.x0 >= CENTRE_INDENT
    )


def _baseline(line: list[LayoutChar]) -> float:
    """Median bottom of the line's dominant-size glyphs."""
    glyphs = [c for c in line if c.bbox is not None]
    sizes = Counter(round(c.size, 1) for c in glyphs)
    size = max(sizes, key=lambda s: (sizes[s], s))
    return median(c.bbox.y1 for c in glyphs if round(c.size, 1) == size and c.bbox is not None)


def _tagged(prev: list[LayoutChar], line: list[LayoutChar]) -> bool:
    """Either line carries a marked-content id, i.e. the PDF is tagged."""
    return any(c.mcid is not None for c in (*prev, *line) if c.bbox is not None)


def _cid_text(text: str) -> str:
    """pdfminer writes "(cid:N)" for a glyph without a Unicode mapping (TeX math fonts);
    use the code point below 127 as PyMuPDF did (CMEX delimiters come out as control
    characters, which the D11/D12 ground truth keeps as equation segments), else drop it."""
    return _CID.sub(lambda m: chr(n) if (n := int(m.group(1))) < 127 else "", text)


def _font_drops(chars: Sequence[dict[str, Any]]) -> dict[str, float]:
    """Per font, how far (points per font size) its glyph boxes hang too low.

    pdfminer places a glyph box at baseline + the font descriptor's Descent; TeX symbol fonts
    (CMSY) declare a Descent near -0.96 em, so "→" sits most of a line below its text line.
    A font whose usual drop (baseline minus box bottom, in sizes) exceeds MAX_DESCENT is moved
    up to NORMAL_DESCENT. Rise (superscripts) is kept: the shift is per font, not per glyph.
    """
    seen: dict[str, Counter[float]] = {}
    for ch in chars:
        m, size = ch.get("matrix"), float(ch.get("size") or 0.0)
        if not ch.get("upright", True) or not m or size <= 0:
            continue
        seen.setdefault(str(ch.get("fontname", "")), Counter())[
            round((float(m[5]) - float(ch["y0"])) / size, 2)
        ] += 1
    drops: dict[str, float] = {}
    for font, counts in seen.items():
        descent = counts.most_common(1)[0][0]
        if descent > MAX_DESCENT:
            drops[font] = descent - NORMAL_DESCENT
    return drops


# --- Ligature repair (ING-2, found on a user PDF 2026-10-16) ---------------------------------
# Some subset TrueType fonts carry a ToUnicode map that sends their ligature glyphs to ASCII
# punctuation ("Ful!lled", "e#ort", "$avor"); which character stands for which ligature changes
# from font to font. The embedded font program still names each glyph in its post table
# (f_i, f_f_i, uniFB01, ...): the repair looks the glyph up through the font's own cmap and, when
# the mapped text is one punctuation character and the glyph is a ligature, uses the letters.
_LIGATURES = {"ff": "ff", "fi": "fi", "fl": "fl", "ffi": "ffi", "ffl": "ffl", "ft": "ft"}
_LIGATURE_UNI = {
    "FB00": "ff",
    "FB01": "fi",
    "FB02": "fl",
    "FB03": "ffi",
    "FB04": "ffl",
    "FB05": "st",
    "FB06": "st",
}
# ING-5: the same ligatures as text-layer code points (U+FB00..U+FB06), decomposed in stage 1.
LIGATURE_CHARS = str.maketrans({chr(int(code, 16)): text for code, text in _LIGATURE_UNI.items()})


def ligature_text(glyph: str) -> str | None:
    """The letters a ligature glyph name stands for ("f_i", "fi", "uniFB01" -> "fi"; any AGL
    underscore name of single letters, "f_f_b" -> "ffb"), else None."""
    name = glyph.split(".")[0]
    if name.startswith("uni") and name[3:].upper() in _LIGATURE_UNI:
        return _LIGATURE_UNI[name[3:].upper()]
    parts = name.split("_")
    if 2 <= len(parts) <= 4 and all(len(p) == 1 and p.isascii() and p.isalpha() for p in parts):
        return "".join(parts)
    return _LIGATURES.get(name)


def _cmap_lookup(sub: bytes, code: int) -> int:
    fmt = struct.unpack(">H", sub[:2])[0]
    if fmt == 0:
        return sub[6 + code] if code < 256 else 0
    if fmt == 6:
        first, count = struct.unpack(">HH", sub[6:10])
        if first <= code < first + count:
            return int(
                struct.unpack(">H", sub[10 + 2 * (code - first) : 12 + 2 * (code - first)])[0]
            )
        return 0
    if fmt == 4:
        n = struct.unpack(">H", sub[6:8])[0] // 2
        arr = [struct.unpack(f">{n}H", sub[o : o + 2 * n]) for o in (14, 16 + 2 * n)]
        ends, starts = arr
        deltas = struct.unpack(f">{n}h", sub[16 + 4 * n : 16 + 6 * n])
        ro_at = 16 + 6 * n
        offsets = struct.unpack(f">{n}H", sub[ro_at : ro_at + 2 * n])
        for i in range(n):
            if starts[i] <= code <= ends[i]:
                if offsets[i] == 0:
                    return (code + deltas[i]) & 0xFFFF
                at = ro_at + 2 * i + offsets[i] + 2 * (code - starts[i])
                gid = struct.unpack(">H", sub[at : at + 2])[0]
                return (gid + deltas[i]) & 0xFFFF if gid else 0
        return 0
    return 0


def truetype_glyph_names(data: bytes) -> dict[int, str]:
    """Character code (0-255) -> glyph name, from a TrueType font's cmap and format-2 post
    tables. Names from the Macintosh standard set (index < 258) are not resolved. Pure."""
    tables: dict[bytes, bytes] = {}
    for i in range(struct.unpack(">H", data[4:6])[0]):
        tag, _, off, length = struct.unpack(">4sIII", data[12 + 16 * i : 28 + 16 * i])
        tables[tag] = data[off : off + length]
    post, cmap = tables.get(b"post", b""), tables.get(b"cmap", b"")
    if len(post) < 34 or struct.unpack(">I", post[:4])[0] != 0x00020000 or len(cmap) < 4:
        return {}
    count = struct.unpack(">H", post[32:34])[0]
    index = struct.unpack(f">{count}H", post[34 : 34 + 2 * count])
    custom, at = [], 34 + 2 * count
    while at < len(post):
        custom.append(post[at + 1 : at + 1 + post[at]].decode("latin-1"))
        at += 1 + post[at]
    subs = {}
    for i in range(struct.unpack(">H", cmap[2:4])[0]):
        plat, enc, off = struct.unpack(">HHI", cmap[4 + 8 * i : 12 + 8 * i])
        subs[(plat, enc)] = cmap[off:]
    sub = subs.get((3, 0)) or subs.get((1, 0)) or subs.get((3, 1))
    if sub is None:
        return {}
    out: dict[int, str] = {}
    for code in range(256):
        gid = _cmap_lookup(sub, code) or _cmap_lookup(sub, 0xF000 | code)
        if 0 < gid < count and index[gid] >= 258 and index[gid] - 258 < len(custom):
            out[code] = custom[index[gid] - 258]
    return out


def repair_ligature(text: str, font: str, fixes: dict[tuple[str, str], str]) -> str:
    """The ligature letters for a glyph ``fixes`` names (font name with prefix, mapped text)."""
    return fixes.get((font, text), text)


def _font_fixes(spec: dict[str, Any]) -> dict[str, str]:
    """For one simple TrueType font: mapped text -> ligature letters, for punctuation-mapped
    ligature glyphs. Empty when anything is missing."""
    from pdfminer.pdffont import PDFTrueTypeFont
    from pdfminer.pdftypes import resolve1

    desc = resolve1(spec.get("FontDescriptor")) or {}
    program = resolve1(desc.get("FontFile2")) if isinstance(desc, dict) else None
    if program is None or "ToUnicode" not in spec:
        return {}
    font = PDFTrueTypeFont(None, spec)  # type: ignore[arg-type]
    umap = getattr(font, "unicode_map", None)
    names = truetype_glyph_names(program.get_data())
    fixes: dict[str, str] = {}
    for code, glyph in names.items():
        letters = ligature_text(glyph)
        mapped = umap.cid2unichr.get(code) if umap is not None else None
        if letters and mapped and len(mapped) == 1 and not mapped.isalnum() and mapped.isascii():
            fixes[mapped] = letters
    return fixes


def _ligature_fixes(page: Any, cache: dict[Any, dict[str, str]]) -> dict[tuple[str, str], str]:
    """(font name, mapped text) -> ligature letters for the page's fonts; a name two fonts
    disagree on is dropped. ``cache`` holds per-font results across pages."""
    from pdfminer.pdftypes import resolve1

    out: dict[tuple[str, str], str] = {}
    bad: set[tuple[str, str]] = set()
    try:
        fonts = resolve1(resolve1(page.page_obj.resources).get("Font")) or {}
        for ref in fonts.values():
            key = getattr(ref, "objid", None) or id(ref)
            spec = resolve1(ref)
            if not isinstance(spec, dict) or str(getattr(spec.get("Subtype"), "name", "")) != (
                "TrueType"
            ):
                continue
            if key not in cache:
                try:
                    cache[key] = _font_fixes(spec)
                except Exception:  # noqa: BLE001 - a damaged font program means no repair
                    cache[key] = {}
            name = str(getattr(spec.get("BaseFont"), "name", spec.get("BaseFont")))
            for mapped, letters in cache[key].items():
                k = (name, mapped)
                if out.get(k, letters) != letters:
                    bad.add(k)
                out[k] = letters
    except Exception:  # noqa: BLE001 - resource walking is best effort
        return {}
    for k in bad:
        out.pop(k, None)
    return out


def _layout_chars(
    page: Any, coords: _Coords, fixes: dict[tuple[str, str], str] | None = None
) -> list[LayoutChar]:
    chars = list(page.chars)
    fixes = fixes or {}
    drops = _font_drops(chars)
    out: list[LayoutChar] = []
    for ch in chars:
        box = coords.obj(ch)
        drop = drops.get(str(ch.get("fontname", "")))
        if drop and ch.get("upright", True):
            up = drop * float(ch.get("size", 0.0))
            box = BBox(box.x0, box.y0 - up, box.x1, box.y1 - up)
        out.append(
            LayoutChar(
                text=repair_ligature(
                    _cid_text(str(ch["text"])), str(ch.get("fontname", "")), fixes
                ),
                bbox=box,
                font=_SUBSET_PREFIX.sub("", str(ch.get("fontname", ""))),
                size=float(ch.get("size", 0.0)),
                upright=bool(ch.get("upright", True)),
                mcid=ch.get("mcid"),
            )
        )
    return out


def _real_tables(tables: Any, coords: _Coords) -> list[BBox]:
    # a ruled frame around prose is one cell; PyMuPDF did not call that a table
    return [
        coords.obj(dict(zip(("x0", "top", "x1", "bottom"), t.bbox, strict=True)))
        for t in tables
        if len(t.rows) >= 2 and max(len(r.cells) for r in t.rows) >= 2
    ]


def _table_bboxes(page: Any, coords: _Coords) -> list[BBox]:
    try:
        return _real_tables(page.find_tables(), coords)
    except Exception:  # noqa: BLE001 - table detection is best effort
        return []


def _hrules(page: Any, coords: _Coords) -> list[BBox]:
    """Thin horizontal strokes and filled rects (table rules) at least RULE_MIN_WIDTH wide."""
    try:
        objs = [*page.lines, *page.rects]
    except Exception:  # noqa: BLE001 - vector analysis is best effort
        return []
    out = []
    for o in objs:
        b = coords.obj(o)
        if b.height <= RULE_MAX_HEIGHT and b.width >= RULE_MIN_WIDTH:
            out.append(b)
    return out


def rule_tables(rules: Sequence[BBox], page_height: float) -> list[BBox]:
    """Booktabs tables (ING-3, tuned 2026-10-16 on pdfplumber): pdfplumber's find_tables needs
    vertical rules, booktabs has none. A stack of >= RULE_STACK_MIN horizontal rules sharing
    their x-extent (each end within RULE_ALIGN points), each within RULE_STACK_GAP of the page
    height of the next, bounds a table: the region from the top rule to the bottom rule. Pure.
    """
    rows: list[BBox] = []
    for r in sorted(rules, key=lambda b: (b.y0, b.x0)):
        if rows and abs(r.y0 - rows[-1].y0) < 1.0 and r.x0 <= rows[-1].x1 + RULE_ALIGN:
            rows[-1] = _union([rows[-1], r])  # pieces of one rule (cmidrule segments, joins)
        else:
            rows.append(r)
    stacks: list[list[BBox]] = []
    for r in rows:
        for st in stacks:
            last = st[-1]
            if (
                abs(r.x0 - last.x0) <= RULE_ALIGN
                and abs(r.x1 - last.x1) <= RULE_ALIGN
                and 0 < r.y0 - last.y0 <= RULE_STACK_GAP * page_height
            ):
                st.append(r)
                break
        else:
            stacks.append([r])
    return [_union(st) for st in stacks if len(st) >= RULE_STACK_MIN]


def _region_lines(region: BBox, lines: Sequence[Sequence[LayoutChar]]) -> tuple[int, int, int]:
    """(lines centred in ``region``, those with a glyph gap wider than COLUMN_GAP font sizes,
    those with none that are at least PROSE_LINE_WIDTH of the region wide). Pure."""
    total = gapped = prose = 0
    for line in lines:
        glyphs = [c for c in line if c.bbox is not None and c.upright]
        if len(glyphs) < 2:
            continue
        box = _union([c.bbox for c in glyphs if c.bbox is not None])
        if not (region.x0 <= box.x_mid <= region.x1 and region.y0 <= box.y_mid <= region.y1):
            continue
        total += 1
        if any(
            b.bbox.x0 - a.bbox.x1 > COLUMN_GAP * max(a.size, b.size, 1.0)
            for a, b in itertools.pairwise(glyphs)
            if a.bbox is not None and b.bbox is not None
        ):
            gapped += 1
        elif region.width > 0 and box.width >= PROSE_LINE_WIDTH * region.width:
            prose += 1
    return total, gapped, prose


def has_columns(region: BBox, lines: Sequence[Sequence[LayoutChar]]) -> bool:
    """Text lines centred in ``region`` have a glyph gap wider than COLUMN_GAP font sizes
    on at least COLUMN_ROWS lines (table rows; a title page framed by rules, even with a
    letter-spaced banner, has fewer). Pure."""
    return _region_lines(region, lines)[1] >= COLUMN_ROWS


def is_prose_region(region: BBox, lines: Sequence[Sequence[LayoutChar]]) -> bool:
    """More than TABLE_PROSE_LINES_MAX lines of running prose lie in ``region`` (a ruled page
    with paragraphs between its rules, not a table). Pure."""
    return _region_lines(region, lines)[2] > TABLE_PROSE_LINES_MAX


def is_text_box(region: BBox, lines: Sequence[Sequence[LayoutChar]], page_width: float) -> bool:
    """``region`` spans at least TEXTBOX_MIN_WIDTH of the page and holds text lines, none with
    a column gap: a framed box around prose (an exercise box), not a table. Pure."""
    total, gapped, _ = _region_lines(region, lines)
    return region.width >= TEXTBOX_MIN_WIDTH * page_width and total > 0 and gapped == 0


def _covered(fig: BBox, boxes: Sequence[BBox]) -> bool:
    """TEXTBOX_COVER of ``fig``'s area lies inside one of ``boxes``."""
    area = _area(fig)
    for b in boxes:
        inter = BBox(max(fig.x0, b.x0), max(fig.y0, b.y0), min(fig.x1, b.x1), min(fig.y1, b.y1))
        overlap = area > 0 and inter.x1 > inter.x0 and inter.y1 > inter.y0
        if overlap and _area(inter) >= TEXTBOX_COVER * area:
            return True
    return False


def _drawing_rects(page: Any, coords: _Coords) -> list[BBox]:
    try:
        rects = [coords.obj(o) for o in [*page.rects, *page.lines]]
        curves = [coords.obj(o) for o in page.curves]
    except Exception:  # noqa: BLE001 - vector analysis is best effort
        return []
    pad = FIGURE_JOIN  # curves (arrows, rounded boxes, plot lines) reach FIGURE_JOIN further
    return [*rects, *(BBox(c.x0 - pad, c.y0 - pad, c.x1 + pad, c.y1 + pad) for c in curves)]


def ocr_page(pdf_path: str | Path, number: int) -> list[Block]:
    """Render page ``number`` of ``pdf_path`` at 300 dpi (pypdfium2) and OCR it into Blocks of
    word Spans (ocr=True)."""
    if not ocr_available():
        raise OCRUnavailable("pytesseract or the tesseract binary is not available")
    import pypdfium2 as pdfium
    import pytesseract

    doc = pdfium.PdfDocument(str(pdf_path))
    try:
        img = doc[number].render(scale=OCR_DPI / 72).to_pil().convert("RGB")
    finally:
        doc.close()
    data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
    scale = 72.0 / OCR_DPI

    grouped: dict[tuple[int, int], dict[int, list[Span]]] = {}
    for i, word in enumerate(data["text"]):
        if not str(word).strip():
            continue
        x0 = data["left"][i] * scale
        y0 = data["top"][i] * scale
        x1 = x0 + data["width"][i] * scale
        y1 = y0 + data["height"][i] * scale
        span = Span(text=str(word), bbox=BBox(x0, y0, x1, y1), font="ocr", size=y1 - y0)
        key = (int(data["block_num"][i]), int(data["par_num"][i]))
        grouped.setdefault(key, {}).setdefault(int(data["line_num"][i]), []).append(span)

    blocks: list[Block] = []
    for index, key in enumerate(sorted(grouped)):
        lines: list[Line] = []
        for line_num in sorted(grouped[key]):
            words = grouped[key][line_num]
            spans = [
                Span(
                    text=w.text + (" " if j < len(words) - 1 else ""),
                    bbox=w.bbox,
                    font=w.font,
                    size=w.size,
                )
                for j, w in enumerate(words)
            ]
            lines.append(Line(spans=spans, bbox=_union([s.bbox for s in spans])))
        bbox = _union([ln.bbox for ln in lines])
        blocks.append(Block(page=number, index=index, bbox=bbox, lines=lines, ocr=True))
    return blocks


def extract_pages(
    pdf_path: str | Path,
    *,
    ocr: bool = True,
    min_text_chars: int = 20,
    on_page: Callable[[int, int], None] | None = None,
    ocr_backend: OCRBackend | None | _Default = DEFAULT_OCR,
) -> list[Page]:
    """Extract every page of ``pdf_path``; OCR pages with fewer than ``min_text_chars``.

    ``on_page(pages_done, total)`` is called after each page is extracted (ING-1 progress).
    """
    pages: list[Page] = []
    font_cache: dict[Any, dict[str, str]] = {}
    with pdfplumber.open(str(pdf_path)) as pdf:
        total = len(pdf.pages)
        for number, pdf_page in enumerate(pdf.pages):
            coords = _Coords(pdf_page)
            fixes = _ligature_fixes(pdf_page, font_cache)
            chars = vector_maths(_layout_chars(pdf_page, coords, fixes), _strokes(pdf_page, coords))
            lines = group_lines(chars)
            ruled = [
                t
                for t in rule_tables(_hrules(pdf_page, coords), float(pdf_page.height))
                if has_columns(t, lines) and not is_prose_region(t, lines)
            ]
            found = _table_bboxes(pdf_page, coords)
            boxes = [t for t in found if is_text_box(t, lines, float(pdf_page.width))]
            found = [t for t in found if t not in boxes and not is_prose_region(t, lines)]
            page = page_from_layout(
                number,
                float(pdf_page.width),
                float(pdf_page.height),
                group_blocks(lines),
                image_bboxes=[coords.obj(im) for im in pdf_page.images],
                table_bboxes=[*found, *ruled],
            )
            page.figure_bboxes = [
                f
                for f in figure_regions(
                    page.image_bboxes, _drawing_rects(pdf_page, coords), page.width, page.height
                )
                if f in page.image_bboxes or not _covered(f, boxes)
            ]
            pdf_page.close()
            if page.text_chars < min_text_chars:
                page.has_text_layer = False
                page.blocks = []
            pages.append(page)
            if on_page is not None:
                on_page(number + 1, total)
    if ocr:
        # ING-2, D28: pages that needs_ocr go to the backend (lazy import avoids a cycle).
        from hearnarro.ingestion.ocr import apply_ocr, default_backend

        backend = default_backend() if isinstance(ocr_backend, _Default) else ocr_backend
        pages, _ = apply_ocr(pdf_path, pages, backend)
    return pages


# Vector-drawn maths in text fonts (MATH-1, ING-3; m5-p3j): a word processor sets a fraction bar
# and a radical as drawn lines, not glyphs, and its numerator, denominator and radicand on three
# baselines, so group_lines splits them. vector_maths rewrites each such construct, before line
# grouping, as one linear run of synthetic glyphs on the bar's axis: "√(…)" for a radical (a
# steep stroke ending where a horizontal overline starts) and "(num)⁄(den)" (U+2044) for a bar
# with glyphs centred above and below it. Small raised or lowered glyphs inside become Unicode
# scripts, and a Greek Σ opening a group is the summation sign ∑. A construct holding a TeX maths
# font glyph is left alone (structure.py reads those from span geometry).
VECTOR_BAR_MAX_HEIGHT = 1.0
VECTOR_BAR_MIN_WIDTH = 3.0
VECTOR_NUM_REACH = 1.7  # numerator script centres within this many sizes above the bar (1.0
# for a full-size glyph, so the prose row above is not a numerator)
VECTOR_STRADDLE = 0.35  # a glyph reaching this many sizes both sides of the bar is on the row
VECTOR_DEN_REACH = 1.2  # denominator glyph centres within this many sizes below it
VECTOR_CENTRE_TOL = 0.3  # numerator and denominator centred on the bar within this share of it
VECTOR_SCRIPT_RATIO = 0.85
VECTOR_ROOT_MIN_HEIGHT = 5.0  # the radical's rising stroke: 5 to 60 points tall and slanted
VECTOR_ROOT_MAX_HEIGHT = 60.0
VECTOR_ROOT_MIN_SLANT = 0.5
VECTOR_UPRIGHT_SHARE = 0.5  # at most this share of a part's glyphs are upright ASCII letters
VECTOR_MAX_GLYPHS = 80  # a larger "construct" is a frame around text, not maths
_SUP_MAP = str.maketrans("0123456789+−-=()n", "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁻⁼⁽⁾ⁿ")
_SUB_MAP = str.maketrans("0123456789+−-=()", "₀₁₂₃₄₅₆₇₈₉₊₋₋₌₍₎")


@dataclass
class _Construct:
    kind: str  # "frac" or "sqrt"
    bar: BBox
    parts: list[set[int]]  # glyph indices: [numerator, denominator] or [radicand]

    @property
    def members(self) -> set[int]:
        return set().union(*self.parts)


def _stroke_radicals(strokes: Sequence[BBox]) -> list[tuple[BBox, BBox]]:
    """(overline, steep stroke) pairs: the stroke's top meets the overline's left end."""
    bars = [s for s in strokes if s.height <= VECTOR_BAR_MAX_HEIGHT and s.width >= 3.0]
    steep = [  # the radical's rising stroke is slanted; a box edge is vertical
        s
        for s in strokes
        if VECTOR_ROOT_MIN_HEIGHT <= s.height <= VECTOR_ROOT_MAX_HEIGHT
        and VECTOR_ROOT_MIN_SLANT <= s.width <= 0.5 * s.height
    ]
    out = []
    for h in bars:
        d = next((d for d in steep if abs(d.x1 - h.x0) <= 0.6 and abs(d.y0 - h.y0) <= 0.6), None)
        if d is not None:
            out.append((h, d))
    return out


def _constructs(chars: Sequence[LayoutChar], strokes: Sequence[BBox]) -> list[_Construct]:
    glyphs = [i for i, c in enumerate(chars) if c.bbox is not None and c.text.strip()]
    rads = _stroke_radicals(strokes)
    over = {id(h) for h, _ in rads}
    out: list[_Construct] = []
    for h, d in rads:
        inside = {
            i
            for i in glyphs
            if h.x0 <= chars[i].bbox.x_mid <= h.x1 + 0.5  # type: ignore[union-attr]
            and h.y0 <= chars[i].bbox.y_mid <= d.y1  # type: ignore[union-attr]
        }
        if inside and len(inside) <= VECTOR_MAX_GLYPHS and _mathy(chars, inside):
            out.append(_Construct("sqrt", h, [inside]))
    for b in strokes:
        if id(b) in over or b.height > VECTOR_BAR_MAX_HEIGHT or b.width < VECTOR_BAR_MIN_WIDTH:
            continue
        y = (b.y0 + b.y1) / 2
        near = [chars[i].size for i in glyphs if abs(chars[i].bbox.y_mid - y) <= 12.0]  # type: ignore[union-attr]
        b_size = max(near, default=0.0)
        num: set[int] = set()
        den: set[int] = set()
        for i in glyphs:
            box = chars[i].bbox
            assert box is not None
            if not b.x0 - 0.5 <= box.x_mid <= b.x1 + 0.5:
                continue
            size = max(chars[i].size, 1.0)
            if box.y0 < y - VECTOR_STRADDLE * size and box.y1 > y + VECTOR_STRADDLE * size:
                continue  # a glyph across the bar is on the text row, not in the fraction
            reach = VECTOR_NUM_REACH if chars[i].size < VECTOR_SCRIPT_RATIO * b_size else 1.0
            if y - reach * size <= box.y_mid < y:
                num.add(i)
            elif y < box.y_mid <= y + VECTOR_DEN_REACH * size:
                den.add(i)
        if (
            num
            and den
            and len(num | den) <= VECTOR_MAX_GLYPHS
            and all(_mathy(chars, p) and _centred(chars, p, b) for p in (num, den))
        ):
            out.append(_Construct("frac", b, [num, den]))
    return [k for k in out if not any(is_math_font(chars[i].font) for i in k.members)]


def _mathy(chars: Sequence[LayoutChar], part: set[int]) -> bool:
    """Most glyphs are maths: italic letters, digits or symbols. Upright text-font letters are
    prose (a booktabs rule between a table's header and body rows is not a fraction bar)."""
    upright = sum(
        1
        for i in part
        if chars[i].text.isascii() and chars[i].text.isalpha() and not font_flags(chars[i].font)[1]
    )
    return upright <= VECTOR_UPRIGHT_SHARE * len(part)


def _centred(chars: Sequence[LayoutChar], part: set[int], bar: BBox) -> bool:
    boxes = [chars[i].bbox for i in part]
    x0 = min(b.x0 for b in boxes if b is not None)
    x1 = max(b.x1 for b in boxes if b is not None)
    y0 = min(b.y0 for b in boxes if b is not None)
    y1 = max(b.y1 for b in boxes if b is not None)
    slack = 0.6 * max(chars[i].size for i in part)

    def runs_on(c: LayoutChar) -> bool:
        """A letter or digit on the part's row just past the bar: the row is text, not a
        numerator or denominator (an underline, a rule under a line)."""
        b = c.bbox
        if b is None or not c.text[:1].isalnum() or bar.x0 - 0.5 <= b.x_mid <= bar.x1 + 0.5:
            return False
        across = min(b.y1, y1) - max(b.y0, y0)
        return across > 0.5 * b.height and x0 - slack <= b.x_mid <= x1 + slack

    return (
        abs((x0 + x1) / 2 - bar.x_mid) <= VECTOR_CENTRE_TOL * bar.width
        and x0 >= bar.x0 - slack
        and x1 <= bar.x1 + slack
        and not any(runs_on(c) for n, c in enumerate(chars) if n not in part)
    )


def _vector_text(chars: Sequence[LayoutChar], k: _Construct, ks: list[_Construct]) -> str:
    if k.kind == "sqrt":
        inner = [j for j in ks if j is not k and j.members <= k.members]
        top = [j for j in inner if not any(j.members < o.members for o in inner)]
        if len(top) == 1 and top[0].kind == "frac" and top[0].members == k.members:
            return "√" + _vector_text(chars, top[0], ks)
        return "√(" + _vector_seq(chars, k.parts[0], ks, k) + ")"
    num, den = (_vector_seq(chars, p, ks, k) for p in k.parts)
    return f"({num})⁄({den})"


def _vector_seq(chars: Sequence[LayoutChar], part: set[int], ks: list[_Construct], own: Any) -> str:
    inner = [j for j in ks if j is not own and j.members <= part and j.members != own.members]
    inner = [j for j in inner if not any(j.members < o.members for o in inner)]
    taken = set().union(*(j.members for j in inner)) if inner else set()
    items: list[tuple[float, str | int]] = [
        (min(chars[i].bbox.x0 for i in j.members), _vector_text(chars, j, ks))  # type: ignore[union-attr]
        for j in inner
    ]
    items += [(chars[i].bbox.x0, i) for i in part - taken]  # type: ignore[union-attr]
    items.sort(key=lambda t: t[0])
    sizes = [chars[i].size for i in part]
    dom = max(sizes)
    out: list[str] = []
    prev_mid: float | None = None
    for n, (_, it) in enumerate(items):
        if isinstance(it, str):
            out.append(it)
            continue
        c = chars[it]
        assert c.bbox is not None
        text = c.text
        if c.size < VECTOR_SCRIPT_RATIO * dom and prev_mid is not None:
            table = _SUP_MAP if c.bbox.y_mid < prev_mid - 0.15 * dom else _SUB_MAP
            mapped = text.translate(table)
            text = mapped if mapped != text or not text.strip() else text
        else:
            prev_mid = c.bbox.y_mid
        nxt = items[n + 1][1] if n + 1 < len(items) else None
        if text == "Σ" and (
            isinstance(nxt, str)
            or (
                nxt is not None
                and chars[nxt].text[:1] in "("
                or (nxt is not None and chars[nxt].text[:1].isalpha())
            )
        ):
            text = "∑"
        out.append(text)
    return "".join(out)


def vector_maths(chars: Sequence[LayoutChar], strokes: Sequence[BBox]) -> list[LayoutChar]:
    """``chars`` with each vector-drawn fraction or radical rewritten as one linear run of
    synthetic glyphs (see VECTOR_BAR_MAX_HEIGHT). Pure."""
    ks = _constructs(chars, strokes)
    top = [k for k in ks if not any(k.members < o.members for o in ks)]
    seen: set[frozenset[int]] = set()
    top = [k for k in top if not (frozenset(k.members) in seen or seen.add(frozenset(k.members)))]  # type: ignore[func-returns-value]
    if not top:
        return list(chars)
    start: dict[int, _Construct] = {}
    drop: set[int] = set()
    for k in top:
        if k.members & drop:
            continue
        start[min(k.members)] = k
        drop |= k.members
    out: list[LayoutChar] = []
    for i, c in enumerate(chars):
        if i in start:
            out.extend(_synthetic(chars, start[i], _vector_text(chars, start[i], ks), ks))
        elif i not in drop:
            out.append(c)
    return out


def _synthetic(
    chars: Sequence[LayoutChar], k: _Construct, text: str, ks: list[_Construct]
) -> list[LayoutChar]:
    members = [chars[i] for i in sorted(k.members)]
    boxes = [c.bbox for c in members if c.bbox is not None]
    dom = max(c.size for c in members)
    first = next(c for c in members if c.size >= VECTOR_SCRIPT_RATIO * dom)
    axis = k.bar
    if k.kind == "sqrt":
        fr = [j for j in ks if j.kind == "frac" and j.members <= k.members]
        if fr:
            axis = fr[0].bar
        else:
            full = [
                c.bbox
                for c in members
                if c.bbox is not None and c.size >= VECTOR_SCRIPT_RATIO * dom
            ]
            mid = median(b.y_mid for b in full)
            axis = BBox(axis.x0, mid, axis.x1, mid)
    y0, y1 = axis.y0 - 0.45 * dom, axis.y0 + 0.55 * dom
    x0 = min(b.x0 for b in boxes)
    x1 = max(max(b.x1 for b in boxes), axis.x1)
    step = (x1 - x0) / max(len(text), 1)
    return [
        LayoutChar(
            text=ch,
            bbox=BBox(x0 + n * step, y0, x0 + (n + 1) * step, y1),
            font=first.font,
            size=dom,
            upright=True,
            mcid=first.mcid,
        )
        for n, ch in enumerate(text)
    ]


def _strokes(page: Any, coords: _Coords) -> list[BBox]:
    """Drawn line segments (not rects: TeX's fraction rules are rects, read from geometry)."""
    try:
        return [coords.obj(o) for o in page.lines]
    except Exception:  # noqa: BLE001 - vector analysis is best effort
        return []
