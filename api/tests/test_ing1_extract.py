"""Stage 1, extract (D1, ING-2)."""

from pathlib import Path

import pymupdf

from hearnarro.ingestion.extract import extract_pages, ocr_available, page_from_dict
from hearnarro.ingestion.models import BBox


def _span(text: str, bbox: tuple, font: str, size: float, flags: int) -> dict:
    return {"text": text, "bbox": bbox, "font": font, "size": size, "flags": flags}


TEXT_DICT = {
    "width": 612.0,
    "height": 792.0,
    "blocks": [
        {
            "number": 0,
            "type": 0,
            "bbox": (72.0, 72.0, 300.0, 100.0),
            "lines": [
                {
                    "bbox": (72.0, 72.0, 300.0, 84.0),
                    "spans": [
                        _span("Bold ", (72.0, 72.0, 100.0, 84.0), "Helvetica", 10.0, 16),
                        _span("italic ", (100.0, 72.0, 140.0, 84.0), "Helvetica", 10.0, 2),
                        _span("1", (140.0, 72.0, 145.0, 78.0), "Helvetica", 6.0, 1),
                    ],
                },
                {
                    "bbox": (72.0, 86.0, 300.0, 100.0),
                    "spans": [
                        _span("Named bold", (72.0, 86.0, 140.0, 100.0), "Times-Bold", 12.0, 0),
                    ],
                },
            ],
        },
        {
            "number": 1,
            "type": 0,
            "bbox": (72.0, 120.0, 540.0, 132.0),
            "lines": [
                {
                    "bbox": (72.0, 120.0, 540.0, 132.0),
                    "spans": [
                        _span("Plain body text.", (72.0, 120.0, 540.0, 132.0), "Times", 10.0, 0)
                    ],
                }
            ],
        },
        {"number": 2, "type": 1, "bbox": (72.0, 200.0, 300.0, 400.0)},
    ],
}


def test_ing2_page_from_dict_builds_blocks_lines_spans() -> None:
    page = page_from_dict(4, 612.0, 792.0, TEXT_DICT)
    assert page.number == 4
    assert (page.width, page.height) == (612.0, 792.0)
    assert len(page.blocks) == 2
    first, second = page.blocks
    assert first.page == 4
    assert [b.index for b in page.blocks] == [0, 1]
    assert first.bbox == BBox(72.0, 72.0, 300.0, 100.0)
    assert first.text == "Bold italic 1\nNamed bold"
    assert second.text == "Plain body text."
    assert all(b.ocr is False for b in page.blocks)


def test_ing2_page_from_dict_span_flags_and_font_names() -> None:
    page = page_from_dict(0, 612.0, 792.0, TEXT_DICT)
    bold, italic, sup = page.blocks[0].lines[0].spans
    named = page.blocks[0].lines[1].spans[0]
    plain = page.blocks[1].lines[0].spans[0]
    assert (bold.bold, bold.italic, bold.superscript) == (True, False, False)
    assert (italic.bold, italic.italic, italic.superscript) == (False, True, False)
    assert (sup.bold, sup.italic, sup.superscript) == (False, False, True)
    assert named.bold is True
    assert named.font == "Times-Bold"
    assert named.size == 12.0
    assert named.bbox == BBox(72.0, 86.0, 140.0, 100.0)
    assert (plain.bold, plain.italic, plain.superscript) == (False, False, False)


def test_ing2_page_from_dict_image_blocks_become_image_bboxes() -> None:
    table = BBox(0, 0, 10, 10)
    page = page_from_dict(0, 612.0, 792.0, TEXT_DICT, table_bboxes=[table])
    assert page.image_bboxes == [BBox(72.0, 200.0, 300.0, 400.0)]
    assert page.table_bboxes == [table]
    assert all(b.type != "image" for b in page.blocks)


def test_ing2_ocr_available_returns_bool() -> None:
    assert isinstance(ocr_available(), bool)


def test_ing2_extract_pages_text_layer(tmp_path: Path) -> None:
    pdf = tmp_path / "hello.pdf"
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Hello world. " * 5)
    doc.save(pdf)
    doc.close()

    pages = extract_pages(pdf, ocr=False)
    assert len(pages) == 1
    assert pages[0].number == 0
    assert pages[0].has_text_layer is True
    text = " ".join(b.text for b in pages[0].blocks)
    assert "Hello world." in text


def test_ing2_extract_pages_blank_page_without_ocr(tmp_path: Path) -> None:
    pdf = tmp_path / "blank.pdf"
    doc = pymupdf.open()
    doc.new_page()
    doc.save(pdf)
    doc.close()

    pages = extract_pages(str(pdf), ocr=False)
    assert len(pages) == 1
    assert pages[0].has_text_layer is False
    assert pages[0].blocks == []
