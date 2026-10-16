"""Stage 1, extract (D1, D13, ING-2)."""

from dataclasses import replace
from pathlib import Path

from hearnarro.ingestion.extract import (
    FIGURE_JOIN,
    NORMAL_DESCENT,
    LayoutChar,
    _font_drops,
    extract_pages,
    figure_regions,
    font_flags,
    group_blocks,
    group_lines,
    has_columns,
    is_math_line,
    ocr_available,
    page_from_layout,
    rule_tables,
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


# --- tuning round 3 on pdfplumber (2026-10-16): grouping, spacing, tables, figures ---


def _texts(blocks: list[list[list[LayoutChar]]]) -> list[str]:
    return [" / ".join("".join(c.text for c in ln) for ln in b) for b in blocks]


def _tag(chars: list[LayoutChar], mcid: int) -> list[LayoutChar]:
    return [replace(c, mcid=mcid) for c in chars]


def test_ing4_tagged_indented_line_opens_block_untagged_hanging_indent_does_not() -> None:
    """MuPDF's text-indent rule: in a tagged PDF a line starting right of the previous one
    opens a block; in an untagged one a 10 pt hanging indent keeps the block."""
    first = _chars("Scott Rose Oliver Borchert", 72, 100, "Times", 10)
    second = _chars("Advanced Network Division", 82, 112, "Times", 10)
    tagged = group_blocks(group_lines([*_tag(first, 1), *_tag(second, 2)]))
    untagged = group_blocks(group_lines([*first, *second]))
    assert len(tagged) == 2
    assert len(untagged) == 1


def test_ing4_untagged_small_indent_opens_block() -> None:
    """A line one point right of a previous line that hung into the margin opens a block."""
    first = _chars("Whether this holds is a question", 71.0, 100, "Times", 10)
    second = _chars("uncertainty. Existing work on it", 72.0, 112, "Times", 10)
    assert len(group_blocks(group_lines([*first, *second]))) == 2


def test_ing4_centred_title_lines_and_reference_entries_split() -> None:
    title = [
        *_chars("Evaluating Multilingual Pipelines Across", 100, 100, "Times", 10),
        *_chars("Subsets of Tasks", 160, 112, "Times", 10),
    ]
    refs = [
        *_chars("[1] Y. Chen, X. Yue, and H. Li,", 72, 300, "Times", 10),
        *_chars("VoiceBench: benchmarking assistants", 86, 312, "Times", 10),
    ]
    assert len(group_blocks(group_lines(title))) == 2
    assert len(group_blocks(group_lines(refs))) == 2


def _glyph(text: str, x0: float, x1: float, top: float, font: str, size: float) -> LayoutChar:
    return LayoutChar(text, BBox(x0, top, x1, top + size), font, size)


def test_ing2_no_word_space_after_tex_relation_but_after_equals() -> None:
    """MuPDF parity: a thick space after a CMSY relation is not a word space ("x ∈S"); the same
    gap after a CMR "=" is ("x = S")."""
    rel = [
        _glyph("x", 100, 105, 100, "CMMI10", 10),
        _glyph("∈", 107.8, 114.5, 100, "CMSY10", 10),
        _glyph("S", 117.3, 123, 100, "CMMI10", 10),
    ]
    eq = [replace(rel[0]), replace(rel[1], text="=", font="CMR10"), replace(rel[2])]
    assert "".join(c.text for c in group_lines(rel)[0]) == "x ∈S"
    assert "".join(c.text for c in group_lines(eq)[0]) == "x = S"


def test_ing2_stacked_scripts_are_read_with_a_space() -> None:
    """A baseline jump of more than BASELINE_JUMP sizes (superscript C over subscript r)."""
    chars = [
        _glyph("V", 100, 106, 100, "CMMI10", 10),
        _glyph("C", 106.5, 111, 97, "CMMI7", 7),
        _glyph("r", 106.5, 110, 104, "CMMI7", 7),
    ]
    assert "".join(c.text for c in group_lines(chars)[0]) == "VC r"


def test_ing2_overstrike_accent_stays_on_the_line() -> None:
    """An accent drawn after its base's neighbour and the letter stepping back under it."""
    chars = [
        _glyph("B", 249.0, 256.1, 214.7, "CMR10", 10),
        _glyph("¨", 256.4, 261.3, 210.0, "CMR10", 10),
        _glyph("u", 256.1, 261.6, 214.7, "CMR10", 10),
        _glyph("h", 261.6, 267.2, 214.7, "CMR10", 10),
    ]
    lines = group_lines(chars)
    assert len(lines) == 1
    assert "".join(c.text for c in lines[0]) == "B¨uh"


def test_ing3_display_math_line_opens_its_own_block() -> None:
    prose = _chars("we model the response as Gaussian, i.e.,", 72, 100, "Times", 10)
    math = _chars("y ~ N(f(x), s)", 150, 112, "CMMI10", 10)
    after = _chars("where f is an unknown function of x", 72, 124, "Times", 10)
    assert is_math_line(math) and not is_math_line(prose)
    assert len(group_blocks(group_lines([*prose, *math, *after]))) == 3


def test_ing2_font_drops_lift_cmsy_boxes_only() -> None:
    """pdfminer hangs CMSY glyph boxes ~0.96 em below the baseline; that font is lifted."""
    chars = [
        {"fontname": "AB+CMSY10", "size": 10.0, "y0": 90.4, "matrix": (10, 0, 0, 10, 0, 100.0)},
        {"fontname": "AB+CMR10", "size": 10.0, "y0": 97.5, "matrix": (10, 0, 0, 10, 0, 100.0)},
    ]
    drops = _font_drops(chars)
    assert set(drops) == {"AB+CMSY10"}
    assert abs(drops["AB+CMSY10"] - (0.96 - NORMAL_DESCENT)) < 1e-6


def test_ing3_booktabs_rule_stack_is_a_table_only_with_column_rows() -> None:
    rules = [BBox(72, y, 300, y + 0.4) for y in (100, 115, 200)]
    region = rule_tables(rules, 792)
    assert region == [BBox(72, 100, 300, 200.4)]
    assert rule_tables(rules[:2], 792) == []  # two rules: a framed title, not a table
    row = [*_chars("Model", 80, 120, "Times", 10), *_chars("0.91", 200, 120, "Times", 10)]
    row2 = [*_chars("Base", 80, 135, "Times", 10), *_chars("0.85", 200, 135, "Times", 10)]
    banner = _chars("C O M P U T E R", 80, 150, "Times", 10)
    assert has_columns(region[0], group_lines([*row, *row2]))
    assert not has_columns(region[0], group_lines(banner))


def test_ing3_figure_regions_curves_join_nearby_parts_rules_never_seed() -> None:
    """Separate boxes within FIGURE_JOIN of a curve form one figure; a wide thin rule alone
    is never a figure part."""
    boxes = [BBox(320, 245, 388, 277), BBox(391, 245, 473, 278)]
    curve = BBox(386 - FIGURE_JOIN, 255 - FIGURE_JOIN, 393 + FIGURE_JOIN, 260 + FIGURE_JOIN)
    regions = figure_regions([], [*boxes, curve], 200, 200)
    assert len(regions) == 1
    assert regions[0].x0 == 320 and regions[0].x1 == 473
    assert figure_regions([], [BBox(10, 50, 190, 50.5)], 200, 200) == []


# --- found on a user book (The Almanack of Naval Ravikant, 2026-10-16) ---


def _tracked(text: str, x: float, gaps: dict[int, float], *, track: float = 1.8) -> list:
    """Caps 6 pt wide on a 9 pt line, ``track`` pt apart; ``gaps`` overrides the gap after
    glyph i (a word space)."""
    out: list[LayoutChar] = []
    for i, ch in enumerate(text):
        out.append(LayoutChar(ch, BBox(x, 100, x + 6, 109), "Times", 9))
        x += 6 + gaps.get(i, track)
    return out


def test_ing2_tracked_caps_line_is_resplit_at_wide_gaps() -> None:
    """Letter-spaced caps get a virtual space between every glyph (1.8 pt > SPACE_GAP); the
    line is re-split so only gaps >= 2x the median inter-glyph gap are word breaks."""
    chars = _tracked("FORMYDAD,", 100, {2: 6.0, 4: 6.0})
    assert ["".join(c.text for c in ln) for ln in group_lines(chars)] == ["FOR MY DAD,"]


def test_ing2_pure_letter_spaced_banner_is_left_for_the_noise_rule() -> None:
    """Every token a single letter ("C O M P U T E R"): left spaced; stage 2 types it noise."""
    chars = _tracked("COMPUTERSECURITY", 100, {7: 6.0})
    assert ["".join(c.text for c in ln) for ln in group_lines(chars)] == [
        "C O M P U T E R S E C U R I T Y"
    ]


def test_ing2_tracked_caps_kerned_pairs_and_trailing_words() -> None:
    """A kerned pair ("OT": no virtual space inside) still joins its word; ordinary words after
    the tracked run keep their spaces."""
    tracked = _tracked("NOTJUSTRIGHT", 100, {1: 0.5, 2: 6.0, 6: 6.0})
    x = tracked[-1].bbox.x1 + 6
    tail = [
        *_chars("is", x, 100, "Times", 9),
        *_chars("a", x + 12, 100, "Times", 9),
        *_chars("product", x + 20, 100, "Times", 9),
    ]
    line = "".join(c.text for c in group_lines([*tracked, *tail])[0])
    assert line == "NOT JUST RIGHT is a product"


def test_ing2_short_spaced_line_is_not_resplit() -> None:
    """Fewer than 6 tokens: left alone (a variable list such as "x y z" stays spaced)."""
    chars = _tracked("ABCD", 100, {})
    assert ["".join(c.text for c in ln) for ln in group_lines(chars)] == ["A B C D"]
