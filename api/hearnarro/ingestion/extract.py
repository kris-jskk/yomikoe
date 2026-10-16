"""Stage 1: extract spans from a PDF, OCR pages without a text layer (D1, D13, ING-2).

Text, fonts, drawings, images and tables come from pdfplumber (MIT; pdfminer.six underneath);
page rendering for OCR comes from pypdfium2 (Apache-2.0/BSD-3). D13 replaced PyMuPDF (AGPL).
"""

from __future__ import annotations

import importlib.util
import re
import shutil
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from statistics import median
from typing import Any

import pdfplumber

from hearnarro.ingestion.models import BBox, Block, Line, Page, Span

OCR_DPI = 300
FIGURE_MIN_FRAC = 0.02  # a drawings union covering less of the page is a rule or a box
FIGURE_MAX_FRAC = 0.80  # ... and one covering this much or more is a page background
# Glyph grouping (D13). pdfminer's own layout analysis (LAParams) splits justified lines at
# wide word gaps and splits inline math into separate boxes, so stage 1 groups pdfplumber's
# glyphs itself, in content-stream order, the way PyMuPDF's text device did: a glyph continues
# the current line when it overlaps it vertically and does not jump backwards; a line joins
# the current block when it overlaps the block, or sits within BLOCK_GAP sizes below it at a
# compatible font size.
SPACE_GAP = 0.15  # a gap wider than this many font sizes between glyphs is a word space
LINE_OVERLAP = 0.3  # min vertical overlap (fraction of the smaller height) to stay on a line
LINE_BACKSTEP = 0.5  # a glyph starting this many sizes left of the previous one ends the line
LINE_MAX_GAP = 10.0  # ... as does a forward jump wider than this many sizes
BLOCK_GAP = 0.5  # max vertical gap between a block and its next line, in font sizes
BLOCK_SIZE_RATIO = 1.25  # max ratio between line font sizes inside one block
SUPERSCRIPT_SIZE_RATIO = 0.75  # a char this much smaller than the line's dominant size ...
SUPERSCRIPT_RAISE = 0.2  # ... whose bottom sits this many dominant sizes higher is raised

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
        if upright:
            k = (c.font, round(c.size, 2), True, raised(c))
        else:  # pdfminer reports a rotated glyph's advance as its size; use the line's
            k = (c.font, dominant, False, False)
        if k != key:
            flush()
            key, text, boxes = k, [], []
        text.append(c.text)
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
    return Page(
        number=number,
        width=width,
        height=height,
        blocks=blocks,
        image_bboxes=list(image_bboxes),
        table_bboxes=list(table_bboxes),
    )


def _char_count(page: Page) -> int:
    return sum(len(s.text.strip()) for b in page.blocks for ln in b.lines for s in ln.spans)


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
    if overlap < LINE_OVERLAP * min(v1 - v0, line_v[1] - line_v[0]):
        return False
    size = max(c.size, prev.size, 1.0)
    gap = _hspan(c)[0] - _hspan(prev)[1]
    return -LINE_BACKSTEP * size <= gap <= LINE_MAX_GAP * size


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
            if gap > SPACE_GAP * max(c.size, prev.size) and lines[-1][-1].bbox is not None:
                lines[-1].append(LayoutChar(" ", None))
            lines[-1].append(c)
            v0, v1 = _vspan(c)
            line_v = (min(line_v[0], v0), max(line_v[1], v1))
        else:
            lines.append([c])
            line_v = _vspan(c)
        prev = c
    for ln in lines:
        while ln and ln[-1].bbox is None:
            ln.pop()
    return [ln for ln in lines if ln]


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
    for line in lines:
        box, size, upright = _line_metrics(line)
        join = False
        if cur_box is not None and upright == cur_upright:
            if box.overlaps(cur_box):
                join = True
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
    return blocks


def _cid_text(text: str) -> str:
    """pdfminer writes "(cid:N)" for a glyph without a Unicode mapping (TeX math fonts);
    use the printable ASCII code point as PyMuPDF did, else drop it."""
    return _CID.sub(lambda m: chr(n) if 32 <= (n := int(m.group(1))) < 127 else "", text)


def _layout_chars(page: Any, coords: _Coords) -> list[LayoutChar]:
    return [
        LayoutChar(
            text=_cid_text(str(ch["text"])),
            bbox=coords.obj(ch),
            font=_SUBSET_PREFIX.sub("", str(ch.get("fontname", ""))),
            size=float(ch.get("size", 0.0)),
            upright=bool(ch.get("upright", True)),
        )
        for ch in page.chars
    ]


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


def _drawing_rects(page: Any, coords: _Coords) -> list[BBox]:
    try:
        objs = [*page.rects, *page.curves, *page.lines]
    except Exception:  # noqa: BLE001 - vector analysis is best effort
        return []
    return [coords.obj(o) for o in objs]


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
    pdf_path: str | Path, *, ocr: bool = True, min_text_chars: int = 20
) -> list[Page]:
    """Extract every page of ``pdf_path``; OCR pages with fewer than ``min_text_chars``."""
    pages: list[Page] = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for number, pdf_page in enumerate(pdf.pages):
            coords = _Coords(pdf_page)
            page = page_from_layout(
                number,
                float(pdf_page.width),
                float(pdf_page.height),
                group_blocks(group_lines(_layout_chars(pdf_page, coords))),
                image_bboxes=[coords.obj(im) for im in pdf_page.images],
                table_bboxes=_table_bboxes(pdf_page, coords),
            )
            page.figure_bboxes = figure_regions(
                page.image_bboxes, _drawing_rects(pdf_page, coords), page.width, page.height
            )
            pdf_page.close()
            if _char_count(page) < min_text_chars:
                page.has_text_layer = False
                page.blocks = []
                if ocr and ocr_available():
                    page.blocks = ocr_page(pdf_path, number)
            pages.append(page)
    return pages
