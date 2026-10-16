"""Stage 1, extract (D1, D13, ING-2)."""

from pathlib import Path

from hearnarro.ingestion.extract import (
    LayoutChar,
    extract_pages,
    font_flags,
    group_blocks,
    group_lines,
    ocr_available,
    page_from_layout,
)
from hearnarro.ingestion.models import BBox

UNIT = Path(__file__).parent / "fixtures" / "unit"


def _chars(
    text: str, x: float, top: float, font: str, size: float, *, upright: bool = True
) -> list[LayoutChar]:
    """One glyph per character, 0.5*size wide, laid left to right on a line at ``top``."""
    out: list[LayoutChar] = []
    for ch in text:
        if ch == " ":
            out.append(LayoutChar(" ", None))
            continue
        w = 0.5 * size
        out.append(LayoutChar(ch, BBox(x, top, x + w, top + size), font, size, upright))
        x += w
    return out


def _boxes() -> list:
    line1 = [
        *_chars("Bold", 72, 72, "ABCDEF+Helvetica-Bold", 10),
        LayoutChar(" ", None),
        *_chars("italic", 100, 72, "Times-Italic", 10),
        *_chars("1", 130, 70, "Helvetica", 6),  # small and raised 2pt -> superscript
    ]
    line2 = _chars("Named bold", 72, 86, "Times-Bold", 12)
    plain = _chars("Plain body text.", 72, 120, "Times", 10)
    return [[line1, line2], [], [plain]]


def test_ing2_page_from_layout_builds_blocks_lines_spans() -> None:
    page = page_from_layout(4, 612.0, 792.0, _boxes())
    assert page.number == 4
    assert (page.width, page.height) == (612.0, 792.0)
    assert len(page.blocks) == 2  # the empty box is skipped
    first, second = page.blocks
    assert first.page == 4
    assert [b.index for b in page.blocks] == [0, 2]  # index = position in the box list
    assert first.text == "Bold italic1\nNamed bold"
    assert second.text == "Plain body text."
    assert first.bbox.x0 == 72 and first.bbox.y0 == 70 and first.bbox.y1 == 98
    assert all(b.ocr is False for b in page.blocks)


def test_ing2_page_from_layout_span_flags_from_font_names() -> None:
    page = page_from_layout(0, 612.0, 792.0, _boxes())
    bold, italic, sup = page.blocks[0].lines[0].spans
    named = page.blocks[0].lines[1].spans[0]
    plain = page.blocks[1].lines[0].spans[0]
    assert bold.text == "Bold " and bold.font == "ABCDEF+Helvetica-Bold"
    assert (bold.bold, bold.italic, bold.superscript) == (True, False, False)
    assert (italic.bold, italic.italic, italic.superscript) == (False, True, False)
    assert (sup.text, sup.bold, sup.italic, sup.superscript) == ("1", False, False, True)
    assert named.bold is True and named.font == "Times-Bold" and named.size == 12.0
    assert named.bbox == BBox(72.0, 86.0, 126.0, 98.0)  # 9 glyphs x 6pt; the space has no box
    assert (plain.bold, plain.italic, plain.superscript) == (False, False, False)


def test_ing2_font_flags() -> None:
    assert font_flags("Helvetica-Bold") == (True, False)
    assert font_flags("Arial,B") == (True, False)
    assert font_flags("NimbusRomNo9L-Medi") == (True, False)
    assert font_flags("Times-BoldItalic") == (True, True)
    assert font_flags("Helvetica-Oblique") == (False, True)
    assert font_flags("NimbusRomNo9L-ReguItal") == (False, True)
    assert font_flags("Times-Roman") == (False, False)


def test_ing2_page_from_layout_records_line_dir_and_bboxes() -> None:
    rotated = [
        LayoutChar("a", BBox(10, 100 + 6 * i, 22, 106 + 6 * i), "T", 9, False) for i in range(3)
    ]
    flat = _chars("Body", 72, 72, "T", 9)
    table = BBox(0, 0, 10, 10)
    image = BBox(72.0, 200.0, 300.0, 400.0)
    page = page_from_layout(
        0, 612, 792, [[rotated], [flat]], image_bboxes=[image], table_bboxes=[table]
    )
    assert page.blocks[0].lines[0].dir == (0.0, 1.0)
    assert page.blocks[1].lines[0].dir == (1.0, 0.0)
    assert page.image_bboxes == [image]
    assert page.table_bboxes == [table]
    assert all(b.type != "image" for b in page.blocks)


def test_ing2_ocr_available_returns_bool() -> None:
    assert isinstance(ocr_available(), bool)


def test_ing2_extract_pages_text_layer() -> None:
    pages = extract_pages(UNIT / "text.pdf", ocr=False)
    assert len(pages) == 1
    page = pages[0]
    assert page.number == 0 and page.has_text_layer is True
    assert (page.width, page.height) == (612.0, 792.0)
    texts = [b.text for b in page.blocks]
    assert texts[0] == "Hello world. Hello world. Hello world."
    # top-left origin: the line drawn at PDF y=720 sits near the top of the page
    assert 60 < page.blocks[0].bbox.y0 < 75
    heading = page.blocks[1].lines[0].spans[0]
    assert heading.text == "Bold heading" and heading.bold is True
    italic, sup = page.blocks[2].lines[0].spans
    assert italic.italic is True and (sup.text, sup.superscript) == ("1", True)
    stamp = page.blocks[3]
    assert stamp.text == "arXiv:1234.5678" and stamp.lines[0].dir != (1.0, 0.0)


def test_ing2_extract_pages_image_becomes_image_and_figure_bbox() -> None:
    page = extract_pages(UNIT / "text.pdf", ocr=False)[0]
    assert len(page.image_bboxes) == 1
    img = page.image_bboxes[0]
    assert (round(img.x0), round(img.y0), round(img.x1), round(img.y1)) == (72, 292, 172, 392)
    assert page.figure_bboxes == page.image_bboxes


def test_ing2_extract_pages_blank_page_without_ocr() -> None:
    pages = extract_pages(str(UNIT / "blank.pdf"), ocr=False)
    assert len(pages) == 1
    assert pages[0].has_text_layer is False
    assert pages[0].blocks == []


def test_ing2_group_lines_keeps_justified_words_and_inserts_spaces() -> None:
    # "For" and "task" are 10pt apart (justified), no space glyph between them
    chars = [*_chars("For", 72, 100, "T", 9), *_chars("task", 95, 100, "T", 9)]
    chars += _chars("Next", 72, 111, "T", 9)
    lines = group_lines(chars)
    assert ["".join(c.text for c in ln) for ln in lines] == ["For task", "Next"]


def test_ing2_group_blocks_splits_on_gap_and_size() -> None:
    body = [_chars("one", 72, 100, "T", 9), _chars("two", 72, 111, "T", 9)]
    far = [_chars("three", 72, 140, "T", 9)]  # 20pt gap: new block
    big = [_chars("Title", 72, 151, "T", 14)]  # size jump: new block
    blocks = group_blocks([*body, *far, *big])
    assert [len(b) for b in blocks] == [2, 1, 1]
