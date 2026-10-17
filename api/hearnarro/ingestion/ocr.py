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
ROW_GAP = 2.0  # same-row one-line groups closer than this many line heights are one line
STACK_MAX_LINES = 3  # two stacked groups of at most this many lines each are joined...
STACK_TOL = 2.0  # ...when one's x-range contains the other's (points of tolerance)
VERTICAL_RATIO = 2.0  # a line this many times taller than wide is rotated text
VERTICAL_MIN_CHARS = 3  # ...when it has at least this many non-space characters


@dataclass(frozen=True)
class OcrLine:
    """One recognized text line; ``bbox`` in PDF points, origin top-left. ``block`` is the
    engine's (block, paragraph) number when it has one: lines with different keys never share a
    ``Block``, so side-by-side columns reach stage 3 as separate blocks (ING-4)."""

    text: str
    bbox: BBox
    block: tuple[int, int] | None = None


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
        lines.append(OcrLine(text=" ".join(w[0] for w in ws), bbox=box, block=key[:2]))
    return lines


class _Default:
    """Sentinel: ``ocr_backend`` not given, use the default engine."""


DEFAULT_OCR = _Default()


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


def is_vertical(line: OcrLine) -> bool:
    """A line much taller than wide with several characters was read from rotated text (an
    arXiv side stamp, an axis label); it becomes a ``Line`` with ``dir=(0, 1)`` so stage 2
    treats it like rotated text from a text layer (margin text is excluded)."""
    b = line.bbox
    chars = len("".join(line.text.split()))
    return chars >= VERTICAL_MIN_CHARS and (b.y1 - b.y0) > VERTICAL_RATIO * (b.x1 - b.x0)


def _gap_groups(lines: Sequence[OcrLine]) -> list[list[OcrLine]]:
    """Sort top to bottom, then left to right; a vertical gap above ``LINE_GAP`` line heights
    starts a new group."""
    groups: list[list[OcrLine]] = []
    prev: OcrLine | None = None
    for ln in sorted(lines, key=lambda x: (x.bbox.y0, x.bbox.x0)):
        height = max(prev.bbox.y1 - prev.bbox.y0, 1.0) if prev else 0.0
        if prev is None or ln.bbox.y0 - prev.bbox.y1 > LINE_GAP * height:
            groups.append([])
        groups[-1].append(ln)
        prev = ln
    return groups


def _to_line(g: OcrLine) -> Line:
    vertical = is_vertical(g)
    size = (g.bbox.x1 - g.bbox.x0) if vertical else (g.bbox.y1 - g.bbox.y0)
    return Line(
        spans=[Span(text=g.text.strip(), bbox=g.bbox, font="ocr", size=size)],
        bbox=g.bbox,
        dir=(0.0, 1.0) if vertical else (1.0, 0.0),
    )


def _merge_row(groups: list[list[OcrLine]]) -> list[list[OcrLine]]:
    """Join one-line groups that sit on the same row with a word-sized horizontal gap (under
    ``ROW_GAP`` line heights) into one line: the engine splits an author row into several
    blocks, which stage 3 would otherwise send to different columns. A column gutter is wider
    than that, so lines in two columns stay apart."""
    singles = sorted(
        (g[0] for g in groups if len(g) == 1 and not is_vertical(g[0])),
        key=lambda x: (x.bbox.y0, x.bbox.x0),
    )
    rest = [g for g in groups if not (len(g) == 1 and not is_vertical(g[0]))]
    rows: list[list[OcrLine]] = []
    for ln in singles:
        height = ln.bbox.y1 - ln.bbox.y0
        for row in rows:
            last = max(row, key=lambda x: x.bbox.x1)
            overlap = min(last.bbox.y1, ln.bbox.y1) - max(last.bbox.y0, ln.bbox.y0)
            small = min(height, last.bbox.y1 - last.bbox.y0)
            gap = ln.bbox.x0 - last.bbox.x1
            if overlap >= 0.5 * small and 0 <= gap < ROW_GAP * max(height, small):
                row.append(ln)
                break
        else:
            rows.append([ln])
    merged = [
        [
            OcrLine(
                text=" ".join(x.text.strip() for x in sorted(row, key=lambda x: x.bbox.x0)),
                bbox=BBox(
                    min(x.bbox.x0 for x in row),
                    min(x.bbox.y0 for x in row),
                    max(x.bbox.x1 for x in row),
                    max(x.bbox.y1 for x in row),
                ),
                block=row[0].block,
            )
        ]
        for row in rows
    ]
    return rest + merged


def _span(g: Sequence[OcrLine]) -> tuple[float, float]:
    return min(x.bbox.x0 for x in g), max(x.bbox.x1 for x in g)


def _merge_stack(groups: list[list[OcrLine]]) -> list[list[OcrLine]]:
    """Join two short groups (at most ``STACK_MAX_LINES`` lines each) stacked under
    ``LINE_GAP`` line heights apart when one's x-range contains the other's: centred
    affiliation lines under an author row, or a logo word over the lines of its caption, which a
    text layer keeps in one block. Two columns never overlap in x, so they are never joined."""
    out: list[list[OcrLine]] = []
    for g in sorted(groups, key=lambda g: (min(x.bbox.y0 for x in g), min(x.bbox.x0 for x in g))):
        host = None
        if len(g) <= STACK_MAX_LINES and not is_vertical(g[0]):
            gx0, gx1 = _span(g)
            top = min(x.bbox.y0 for x in g)
            for cand in out:
                if len(cand) > STACK_MAX_LINES or is_vertical(cand[0]):
                    continue
                last = max(cand, key=lambda x: x.bbox.y1)
                height = max(last.bbox.y1 - last.bbox.y0, 1.0)
                cx0, cx1 = _span(cand)
                inside = cx0 - STACK_TOL <= gx0 and gx1 <= cx1 + STACK_TOL
                around = gx0 - STACK_TOL <= cx0 and cx1 <= gx1 + STACK_TOL
                if 0 <= top - last.bbox.y1 <= LINE_GAP * height and (inside or around):
                    host = cand
                    break
        if host is None:
            out.append(list(g))
        else:
            host.extend(g)
    return out


def lines_to_blocks(page_number: int, lines: Sequence[OcrLine]) -> list[Block]:
    """Lines are first split by the engine's block number, so two columns the engine
    segmented apart stay apart for stage 3's gutter detection; lines without a key form one
    group; rotated lines (``is_vertical``) never share a group with upright ones. Within each,
    a vertical gap above ``LINE_GAP`` line heights starts a new block; one-line blocks on one
    row are then joined (``_merge_row``), and short stacked groups nested in x are joined
    (``_merge_stack``).
    Blocks are numbered top to bottom, then left to right. Every block is ``ocr=True``."""
    keyed: dict[tuple[int | None, bool], list[OcrLine]] = {}
    for ln in lines:
        if ln.text.strip():
            block = ln.block[0] if ln.block is not None else None
            keyed.setdefault((block, is_vertical(ln)), []).append(ln)
    groups = _merge_row([g for key_lines in keyed.values() for g in _gap_groups(key_lines)])
    groups = _merge_stack(groups)
    groups.sort(key=lambda g: (min(x.bbox.y0 for x in g), min(x.bbox.x0 for x in g)))
    blocks: list[Block] = []
    for index, group in enumerate(groups):
        out = [_to_line(g) for g in group]
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
