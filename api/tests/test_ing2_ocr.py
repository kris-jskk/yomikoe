"""OCR fallback behind OCRBackend (ING-2, D28 proposed).

Spec: _agent/specs/m4-library-interfaces.md §3, row "OCR fallback". Stage 1 reports per page
``text_chars``; a page with fewer than 20 and ink coverage above 0.5 % (100 dpi grayscale,
pixels under 128) goes to ``OCRBackend.recognize(page_image) -> list[OcrLine]``. With no engine
the page stays empty and ``IngestResult.ocr_skipped_pages`` counts it. ``OcrLine.bbox`` is in
PDF points, origin top-left (the ``BBox`` convention).

``hearnarro.ingestion.ocr`` is imported inside each test (``_ocr()``) so that, while it does
not exist, every test fails on the missing module instead of the file failing to collect.

The real-engine test is ``@pytest.mark.ocr`` and is skipped unless ``tesseract`` is on PATH.
"""

import importlib
import logging
import shutil
from pathlib import Path
from types import ModuleType

import pytest
from PIL import Image, ImageDraw

from hearnarro.ingestion.extract import extract_pages
from hearnarro.ingestion.models import BBox
from hearnarro.ingestion.pipeline import ingest

PDFS = Path(__file__).parent / "fixtures" / "pdfs"
UNIT = Path(__file__).parent / "fixtures" / "unit"
SCANNED = sorted(PDFS.glob("scanned_0[1-5]_*.pdf"))
SCANNED_01 = PDFS / "scanned_01_seahelm_audio.pdf"

TOP = "The first line of the recognized page is read first."
MIDDLE = "The middle line of the recognized page comes second."
BOTTOM = "The last line of the recognized page is read at the end."


def _ocr() -> ModuleType:
    """hearnarro.ingestion.ocr: OCRBackend, FakeOCRBackend, TesseractBackend, OcrLine,
    ink_coverage, needs_ocr."""
    return importlib.import_module("hearnarro.ingestion.ocr")


def _line(ocr: ModuleType, text: str, y: float):
    return ocr.OcrLine(text=text, bbox=BBox(72.0, y, 540.0, y + 12.0))


# ---------------------------------------------------------------------------------------
# Decision: text_chars and ink coverage
# ---------------------------------------------------------------------------------------


def test_ing2_ink_coverage_counts_dark_pixels() -> None:
    ocr = _ocr()
    white = Image.new("L", (100, 100), 255)
    assert ocr.ink_coverage(white) == 0.0
    inked = white.copy()
    ImageDraw.Draw(inked).rectangle((0, 0, 9, 99), fill=0)  # 10 of 100 columns
    assert ocr.ink_coverage(inked) == pytest.approx(0.10, abs=1e-6)
    grey = Image.new("L", (100, 100), 128)  # not under 128
    assert ocr.ink_coverage(grey) == 0.0


@pytest.mark.parametrize(
    ("text_chars", "ink", "expected"),
    [
        (0, 0.10, True),
        (19, 0.006, True),
        (20, 0.90, False),  # a text layer: never OCR
        (5, 0.0, False),  # blank page
        (0, 0.005, False),  # "above 0.5 %": the boundary is not enough
    ],
)
def test_ing2_needs_ocr_rule(text_chars: int, ink: float, expected: bool) -> None:
    ocr = _ocr()
    assert ocr.needs_ocr(text_chars, ink) is expected


def test_ing2_stage1_reports_text_chars() -> None:
    text_page = extract_pages(UNIT / "text.pdf", ocr=False)[0]
    assert text_page.text_chars >= 20
    scanned = extract_pages(SCANNED_01, ocr=False)
    assert [p.text_chars for p in scanned] == [0, 0]


# ---------------------------------------------------------------------------------------
# Routing pages to the backend
# ---------------------------------------------------------------------------------------


def test_ing2_fake_backend_is_an_ocr_backend() -> None:
    ocr = _ocr()
    fake = ocr.FakeOCRBackend([_line(ocr, TOP, 100.0)])
    assert isinstance(fake, ocr.OCRBackend)
    assert fake.recognize(Image.new("L", (10, 10), 255)) == [_line(ocr, TOP, 100.0)]


@pytest.mark.parametrize("pdf", SCANNED, ids=lambda p: p.stem)
def test_ing2_scanned_pages_go_to_backend(pdf: Path) -> None:
    ocr = _ocr()
    fake = ocr.FakeOCRBackend([_line(ocr, TOP, 100.0)])
    pages = extract_pages(pdf, ocr_backend=fake)
    assert len(fake.calls) == len(pages) == 2
    assert all(b.ocr for p in pages for b in p.blocks)


def test_ing2_blank_page_is_not_sent_to_backend() -> None:
    ocr = _ocr()
    fake = ocr.FakeOCRBackend([_line(ocr, TOP, 100.0)])
    pages = extract_pages(UNIT / "blank.pdf", ocr_backend=fake)
    assert fake.calls == []
    assert all(not p.blocks for p in pages)


def test_ing2_text_layer_page_is_not_sent_to_backend() -> None:
    ocr = _ocr()
    fake = ocr.FakeOCRBackend([_line(ocr, TOP, 100.0)])
    extract_pages(UNIT / "text.pdf", ocr_backend=fake)
    assert fake.calls == []


def test_ing2_fake_lines_become_blocks_in_reading_order() -> None:
    """Lines handed over bottom, top, middle are read top to bottom."""
    ocr = _ocr()
    fake = ocr.FakeOCRBackend(
        [_line(ocr, BOTTOM, 500.0), _line(ocr, TOP, 100.0), _line(ocr, MIDDLE, 300.0)]
    )
    result = ingest(SCANNED_01, ocr_backend=fake)
    joined = " ".join(s.text for s in result.segments)
    assert TOP in joined and MIDDLE in joined and BOTTOM in joined
    assert joined.index(TOP) < joined.index(MIDDLE) < joined.index(BOTTOM)
    assert result.ocr_skipped_pages == 0


def test_ing2_no_engine_leaves_page_empty_and_counts_it(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO)
    result = ingest(SCANNED_01, ocr_backend=None)
    assert result.ocr_skipped_pages == 2
    assert result.segments == []
    assert all(not p.blocks for p in result.pages)
    assert any("ocr" in r.getMessage().lower() for r in caplog.records)


def test_ing2_no_engine_text_document_skips_nothing() -> None:
    assert ingest(UNIT / "text.pdf", ocr_backend=None).ocr_skipped_pages == 0


def test_ing2_tesseract_availability_follows_path() -> None:
    ocr = _ocr()
    assert ocr.TesseractBackend.available() is (shutil.which("tesseract") is not None)


# ---------------------------------------------------------------------------------------
# Real engine (D28): skipped unless the tesseract binary is on PATH
# ---------------------------------------------------------------------------------------


@pytest.mark.ocr
@pytest.mark.skipif(shutil.which("tesseract") is None, reason="tesseract not on PATH (D28)")
def test_ing2_tesseract_reads_scanned_01() -> None:
    ocr = _ocr()
    result = ingest(SCANNED_01, ocr_backend=ocr.TesseractBackend())
    words = " ".join(s.text for s in result.segments).lower()
    assert result.ocr_skipped_pages == 0
    assert "audio" in words and "singapore" in words
