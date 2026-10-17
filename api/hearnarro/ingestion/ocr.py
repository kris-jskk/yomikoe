"""OCR fallback behind ``OCRBackend`` (ING-2, D28).

Rule (``_agent/specs/m4-library-interfaces.md`` §3, row "OCR fallback"): a page whose text
layer has fewer than ``MIN_TEXT_CHARS`` non-space glyphs and whose render at ``INK_DPI``
(grayscale) has more than ``MIN_INK`` of its pixels under ``INK_LEVEL`` is sent to
``OCRBackend.recognize(page_image) -> list[OcrLine]``. With no engine the page stays empty, it is
counted in ``ocr_skipped_pages`` and a log line says so. Pages are rendered with pypdfium2 (D13).

``OcrLine.bbox`` is in PDF points, origin top-left (the ``BBox`` convention). Images handed to a
backend carry their render resolution in ``image.info["dpi"]`` so a pixel-space engine can
convert its boxes.
"""

from __future__ import annotations

import csv
import io
import logging
import shutil
import subprocess
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

from PIL import Image

from hearnarro.ingestion.models import BBox, Block, Line, Page, Span

log = logging.getLogger(__name__)

MIN_TEXT_CHARS = 20  # D28: fewer non-space glyphs than this and the page may be a scan
MIN_INK = 0.005  # D28: ink coverage must be strictly above 0.5 %
INK_LEVEL = 128  # D28: a pixel is ink when its grayscale value is under this
INK_DPI = 100  # D28: resolution of the ink-coverage render
OCR_DPI = 300  # resolution of the image handed to the backend
LINE_GAP = 1.5  # lines further apart than this many line heights start a new block
SCAN_AREA = 0.5  # an image covering more of the page than this is the scan itself


@dataclass(frozen=True)
class OcrLine:
    """One recognized text line; ``bbox`` in PDF points, origin top-left."""

    text: str
    bbox: BBox


@runtime_checkable
class OCRBackend(Protocol):
    def recognize(self, page_image: Image.Image) -> list[OcrLine]: ...


class FakeOCRBackend:
    """Returns the same fixture lines for every page; records each image it was given."""

    def __init__(self, lines: Sequence[OcrLine]) -> None:
        self.lines = list(lines)
        self.calls: list[Image.Image] = []

    def recognize(self, page_image: Image.Image) -> list[OcrLine]:
        self.calls.append(page_image)
        return list(self.lines)


class TesseractBackend:
    """``tesseract <png> stdout --psm 3 tsv`` as a subprocess (Apache-2.0 binary, optional)."""

    def __init__(self, binary: str | None = None, timeout: float = 120.0) -> None:
        self.binary = binary or shutil.which("tesseract")
        self.timeout = timeout

    @staticmethod
    def available() -> bool:
        return shutil.which("tesseract") is not None

    def recognize(self, page_image: Image.Image) -> list[OcrLine]:
        if self.binary is None:
            raise RuntimeError("tesseract binary not on PATH")
        dpi = float(page_image.info.get("dpi", (OCR_DPI, OCR_DPI))[0]) or OCR_DPI
        with tempfile.TemporaryDirectory() as tmp:
            png = Path(tmp) / "page.png"
            page_image.save(png, dpi=(dpi, dpi))
            proc = subprocess.run(
                [self.binary, str(png), "stdout", "--psm", "3", "tsv"],
                capture_output=True,
                text=True,
                timeout=self.timeout,
                check=True,
            )
        return parse_tsv(proc.stdout, scale=72.0 / dpi)


def parse_tsv(tsv: str, *, scale: float) -> list[OcrLine]:
    """Group tesseract TSV word rows (level 5) into lines by (block, par, line) number;
    pixel boxes are multiplied by ``scale`` to give PDF points."""
    words: dict[tuple[int, int, int], list[tuple[str, float, float, float, float]]] = {}
    for row in csv.DictReader(io.StringIO(tsv), delimiter="\t", quoting=csv.QUOTE_NONE):
        text = (row.get("text") or "").strip()
        if row.get("level") != "5" or not text:
            continue
        x0, y0 = float(row["left"]) * scale, float(row["top"]) * scale
        x1 = x0 + float(row["width"]) * scale
        y1 = y0 + float(row["height"]) * scale
        key = (int(row["block_num"]), int(row["par_num"]), int(row["line_num"]))
        words.setdefault(key, []).append((text, x0, y0, x1, y1))
    lines: list[OcrLine] = []
    for key in sorted(words):
        ws = words[key]
        box = BBox(
            min(w[1] for w in ws),
            min(w[2] for w in ws),
            max(w[3] for w in ws),
            max(w[4] for w in ws),
        )
        lines.append(OcrLine(text=" ".join(w[0] for w in ws), bbox=box))
    return lines


def default_backend() -> OCRBackend | None:
    """The engine used when the caller does not name one: tesseract if on PATH, else none."""
    return TesseractBackend() if TesseractBackend.available() else None


def ink_coverage(image: Image.Image) -> float:
    """Fraction of pixels whose grayscale value is under ``INK_LEVEL``."""
    gray = image.convert("L")
    hist = gray.histogram()
    total = sum(hist)
    return sum(hist[:INK_LEVEL]) / total if total else 0.0


def needs_ocr(text_chars: int, ink: float) -> bool:
    """D28: too little text layer and visible ink."""
    return text_chars < MIN_TEXT_CHARS and ink > MIN_INK


def page_text_chars(page: Page) -> int:
    """``Page.text_chars`` when stage 1 reports it; otherwise counted from the page's glyphs.
    Stage 1 empties a page under the threshold, so an emptied page counts as 0."""
    reported = getattr(page, "text_chars", None)
    if reported is not None:
        return int(reported)
    if not page.has_text_layer:
        return 0
    return sum(
        len("".join(s.text.split())) for b in page.blocks for ln in b.lines for s in ln.spans
    )


def render_page(pdf_path: str | Path, number: int, dpi: int, *, grayscale: bool) -> Image.Image:
    import pypdfium2 as pdfium

    doc = pdfium.PdfDocument(str(pdf_path))
    try:
        image = doc[number].render(scale=dpi / 72, grayscale=grayscale).to_pil()
    finally:
        doc.close()
    image = image.convert("L" if grayscale else "RGB")
    image.info["dpi"] = (dpi, dpi)
    return image


def lines_to_blocks(page_number: int, lines: Sequence[OcrLine]) -> list[Block]:
    """Sort lines top to bottom, then left to right; a vertical gap above ``LINE_GAP`` line
    heights starts a new block. Every block is marked ``ocr=True``."""
    groups: list[list[OcrLine]] = []
    prev: OcrLine | None = None
    for ln in sorted((x for x in lines if x.text.strip()), key=lambda x: (x.bbox.y0, x.bbox.x0)):
        height = max(prev.bbox.y1 - prev.bbox.y0, 1.0) if prev else 0.0
        if prev is None or ln.bbox.y0 - prev.bbox.y1 > LINE_GAP * height:
            groups.append([])
        groups[-1].append(ln)
        prev = ln
    blocks: list[Block] = []
    for index, group in enumerate(groups):
        out = [
            Line(
                spans=[
                    Span(text=g.text.strip(), bbox=g.bbox, font="ocr", size=g.bbox.y1 - g.bbox.y0)
                ],
                bbox=g.bbox,
            )
            for g in group
        ]
        box = BBox(
            min(g.bbox.x0 for g in group),
            min(g.bbox.y0 for g in group),
            max(g.bbox.x1 for g in group),
            max(g.bbox.y1 for g in group),
        )
        blocks.append(Block(page=page_number, index=index, bbox=box, lines=out, ocr=True))
    return blocks


def _is_scan(box: BBox, page_area: float) -> bool:
    area = max(box.x1 - box.x0, 0.0) * max(box.y1 - box.y0, 0.0)
    return page_area > 0 and area / page_area > SCAN_AREA


def apply_ocr(
    pdf_path: str | Path, pages: list[Page], backend: OCRBackend | None
) -> tuple[list[Page], int]:
    """Replace the blocks of every page that ``needs_ocr`` with the backend's lines.

    Returns ``(pages, skipped)``; ``skipped`` counts pages that needed OCR while no engine was
    available (they are left empty). Pages are modified in place.
    """
    skipped = 0
    for page in pages:
        chars = page_text_chars(page)
        if chars >= MIN_TEXT_CHARS:
            continue
        ink = ink_coverage(render_page(pdf_path, page.number, INK_DPI, grayscale=True))
        if not needs_ocr(chars, ink):
            continue
        page.has_text_layer = False
        page.blocks = []
        if backend is None:
            skipped += 1
            continue
        # The scan image is the page, not a figure in it: drop it from the D12 figure regions
        # so the recognized text is not classified as figure text.
        page_area = page.width * page.height
        page.figure_bboxes = [b for b in page.figure_bboxes if not _is_scan(b, page_area)]
        page.image_bboxes = [b for b in page.image_bboxes if not _is_scan(b, page_area)]
        image = render_page(pdf_path, page.number, OCR_DPI, grayscale=False)
        page.blocks = lines_to_blocks(page.number, backend.recognize(image))
    if skipped:
        log.info(
            "ocr: %d page(s) of %s need OCR but no engine is available; left empty (ING-2)",
            skipped,
            Path(pdf_path).name,
        )
    return pages, skipped
