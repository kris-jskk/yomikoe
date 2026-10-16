"""Stage 1: extract spans from a PDF, OCR pages without a text layer (D1, ING-2)."""

from __future__ import annotations

import importlib.util
import shutil
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pymupdf

from hearnarro.ingestion.models import BBox, Block, Line, Page, Span

# PyMuPDF prints a one-time pymupdf_layout recommendation to stdout from find_tables();
# it would corrupt `hearnarro dump --jsonl`, so disable it.
pymupdf.no_recommend_layout()

OCR_DPI = 300
_FLAG_SUPERSCRIPT = 1
_FLAG_ITALIC = 2
_FLAG_BOLD = 16


class OCRUnavailable(RuntimeError):
    """Raised when OCR is required but pytesseract or the tesseract binary is missing."""


def ocr_available() -> bool:
    """True when pytesseract is importable AND the tesseract binary is on PATH."""
    try:
        has_module = importlib.util.find_spec("pytesseract") is not None
    except (ImportError, ValueError):
        has_module = False
    return has_module and shutil.which("tesseract") is not None


def _span_from_dict(raw: dict[str, Any]) -> Span:
    flags = int(raw.get("flags", 0))
    font = str(raw.get("font", ""))
    return Span(
        text=str(raw.get("text", "")),
        bbox=BBox(*raw["bbox"]),
        font=font,
        size=float(raw.get("size", 0.0)),
        bold=bool(flags & _FLAG_BOLD) or "Bold" in font,
        italic=bool(flags & _FLAG_ITALIC) or "Italic" in font,
        superscript=bool(flags & _FLAG_SUPERSCRIPT),
    )


def _line_dir(raw: dict[str, Any]) -> tuple[float, float]:
    d = raw.get("dir", (1.0, 0.0))
    return (float(d[0]), float(d[1]))


def page_from_dict(
    number: int,
    width: float,
    height: float,
    text_dict: dict[str, Any],
    image_bboxes: Sequence[BBox] = (),
    table_bboxes: Sequence[BBox] = (),
) -> Page:
    """Build a Page from a PyMuPDF ``page.get_text("dict")`` payload (pure)."""
    images = list(image_bboxes)
    blocks: list[Block] = []
    for index, raw in enumerate(text_dict.get("blocks", [])):
        if raw.get("type", 0) == 1:
            images.append(BBox(*raw["bbox"]))
            continue
        lines = [
            Line(
                spans=[_span_from_dict(s) for s in ln.get("spans", [])],
                bbox=BBox(*ln["bbox"]),
                dir=_line_dir(ln),
            )
            for ln in raw.get("lines", [])
        ]
        lines = [ln for ln in lines if ln.spans]
        if not lines:
            continue
        blocks.append(Block(page=number, index=index, bbox=BBox(*raw["bbox"]), lines=lines))
    return Page(
        number=number,
        width=width,
        height=height,
        blocks=blocks,
        image_bboxes=images,
        table_bboxes=list(table_bboxes),
    )


def _char_count(page: Page) -> int:
    return sum(len(s.text.strip()) for b in page.blocks for ln in b.lines for s in ln.spans)


def _table_bboxes(page: pymupdf.Page) -> list[BBox]:
    try:
        return [BBox(*t.bbox) for t in page.find_tables().tables]
    except Exception:  # noqa: BLE001 - table detection is best effort
        return []


def ocr_page(page: pymupdf.Page, number: int) -> list[Block]:
    """Rasterize ``page`` at 300 dpi and OCR it into Blocks of word Spans (ocr=True)."""
    if not ocr_available():
        raise OCRUnavailable("pytesseract or the tesseract binary is not available")
    import pytesseract
    from PIL import Image

    pix = page.get_pixmap(dpi=OCR_DPI)
    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
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


def _union(boxes: Sequence[BBox]) -> BBox:
    return BBox(
        min(b.x0 for b in boxes),
        min(b.y0 for b in boxes),
        max(b.x1 for b in boxes),
        max(b.y1 for b in boxes),
    )


def extract_pages(
    pdf_path: str | Path, *, ocr: bool = True, min_text_chars: int = 20
) -> list[Page]:
    """Extract every page of ``pdf_path``; OCR pages with fewer than ``min_text_chars``."""
    pages: list[Page] = []
    with pymupdf.open(str(pdf_path)) as doc:
        for number, pdf_page in enumerate(doc):
            text_dict = pdf_page.get_text("dict")
            page = page_from_dict(
                number,
                float(pdf_page.rect.width),
                float(pdf_page.rect.height),
                text_dict,
                table_bboxes=_table_bboxes(pdf_page),
            )
            if _char_count(page) < min_text_chars:
                page.has_text_layer = False
                page.blocks = []
                if ocr and ocr_available():
                    page.blocks = ocr_page(pdf_page, number)
            pages.append(page)
    return pages
