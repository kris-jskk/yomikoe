"""Stage 2, classify (ING-3). Pages are 612 x 792 pt; bands are the top/bottom 8%."""

import pytest

from hearnarro.ingestion.classify import (
    PAGE_NUMBER_RE,
    body_median_size,
    classify_pages,
    normalize_key,
    repeated_band_texts,
)
from hearnarro.ingestion.models import BBox, Block, Page
from tests.conftest import make_block, make_page, make_span

FILLER = "This sentence is ordinary body text set in the document's main size."


def _filler(page: int, start_index: int) -> list[Block]:
    """Four long size-10 body blocks so the document median is 10."""
    return [
        make_block(page, start_index + i, [FILLER, FILLER, FILLER], y0=420 + i * 40)
        for i in range(4)
    ]


def _doc(*extra: Block, image_bboxes=(), table_bboxes=()) -> list[Page]:
    blocks = list(extra) + _filler(0, len(extra))
    return [make_page(0, blocks, image_bboxes=image_bboxes, table_bboxes=table_bboxes)]


def _type_of(pages: list[Page], index: int) -> str:
    return next(b for b in pages[0].blocks if b.index == index).type


def test_ing3_normalize_key_keeps_digits() -> None:
    assert normalize_key("  Journal  of\nThings 3 ") == "journal of things 3"


def test_ing3_body_median_size_is_document_wide_and_char_weighted() -> None:
    p0 = make_page(0, [make_block(0, 0, [[make_span("x" * 100, 72, 400, 540, 412, size=10.0)]])])
    p1 = make_page(
        1,
        [
            make_block(1, 0, [[make_span("y" * 10, 72, 100, 200, 124, size=20.0)]]),
            make_block(1, 1, [[make_span("z" * 10, 72, 200, 200, 224, size=20.0)]]),
        ],
    )
    # Unweighted median of [10, 20, 20] is 20, page-1 median is 20; weighted by chars it is 10.
    assert body_median_size([p0, p1]) == pytest.approx(10.0)


def _five_page_doc(header_size: float = 10.0) -> list[Page]:
    pages = []
    for n in range(5):
        blocks = _filler(n, 2)
        if n < 4:
            blocks.insert(0, make_block(n, 0, ["Journal of Things"], y0=30, size=header_size))
        if n >= 3:
            blocks.insert(1, make_block(n, 1, ["Confidential draft"], y0=750))
        pages.append(make_page(n, blocks))
    return pages


def test_ing3_repeated_band_texts_needs_three_pages() -> None:
    assert repeated_band_texts(_five_page_doc()) == {normalize_key("Journal of Things")}


def test_ing3_header_rule_wins_over_heading_size() -> None:
    pages = classify_pages(_five_page_doc(header_size=16.0))
    for page in pages[:4]:
        assert next(b for b in page.blocks if b.index == 0).type == "header"
    # Bottom-band text on only two pages and not a page number: not a footer.
    for page in pages[3:]:
        assert next(b for b in page.blocks if b.index == 1).type == "body"


@pytest.mark.parametrize("text", ["3", "Page 12", "page 4", "7 of 20", " 12 "])
def test_ing3_page_number_regex_matches(text: str) -> None:
    assert PAGE_NUMBER_RE.match(text.strip())


@pytest.mark.parametrize("text", ["Chapter 3", "3 apples", "Figure 2", "2024 was a year"])
def test_ing3_page_number_regex_rejects(text: str) -> None:
    assert not PAGE_NUMBER_RE.match(text.strip())


def test_ing3_page_numbers_in_band_are_header_footer_but_not_outside() -> None:
    pages = classify_pages(
        _doc(
            make_block(0, 0, ["Page 12"], y0=20),
            make_block(0, 1, ["7 of 20"], y0=760),
            make_block(0, 2, ["3"], y0=750, x0=300, width=12),
            make_block(0, 3, ["2024"], y0=300),
        )
    )
    assert _type_of(pages, 0) == "header"
    assert _type_of(pages, 1) == "footer"
    assert _type_of(pages, 2) == "footer"
    assert _type_of(pages, 3) == "body"


def test_ing3_heading_by_font_size() -> None:
    pages = classify_pages(
        _doc(
            make_block(0, 0, ["Results and discussion of the experiment."], y0=100, size=12.0),
            make_block(0, 1, ["A sentence in slightly larger type."], y0=150, size=11.0),
        )
    )
    assert _type_of(pages, 0) == "heading"  # 1.2x median
    assert _type_of(pages, 1) == "body"  # 1.1x median, below 1.15x


def test_ing3_heading_by_bold_short_no_period() -> None:
    long_bold = "This bold line has far more than twelve words in it so it is not a heading"
    pages = classify_pages(
        _doc(
            make_block(0, 0, ["Related Work"], y0=100, bold=True),
            make_block(0, 1, ["This is bold."], y0=150, bold=True),
            make_block(0, 2, [long_bold], y0=200, bold=True),
        )
    )
    assert _type_of(pages, 0) == "heading"
    assert _type_of(pages, 1) == "body"
    assert _type_of(pages, 2) == "body"


def test_ing3_caption_needs_nearby_image() -> None:
    image = BBox(72, 100, 300, 300)
    pages = classify_pages(
        _doc(
            make_block(0, 0, ["Figure 1: Growth over time."], y0=310, width=228),
            make_block(0, 1, ["Figure 1: Growth over time."], y0=700, x0=320, width=200),
            image_bboxes=[image],
        )
    )
    assert _type_of(pages, 0) == "caption"
    assert _type_of(pages, 1) == "body"


def test_ing3_footnote_by_small_size_low_on_page() -> None:
    pages = classify_pages(
        _doc(
            make_block(0, 0, ["See the appendix for the full derivation."], y0=650, size=8.0),
            make_block(0, 1, ["See the appendix for the full derivation."], y0=300, size=8.0),
        )
    )
    assert _type_of(pages, 0) == "footnote"
    assert _type_of(pages, 1) == "body"


def test_ing3_footnote_by_leading_superscript_digit() -> None:
    """Low on the page a leading superscript digit marks a footnote; in the upper half
    (tuned 2026-10-16) it is an affiliation line under the authors."""
    low = [
        make_span("2", 72, 600, 77, 606, size=6.0, superscript=True),
        make_span("Further details are given elsewhere.", 78, 600, 400, 612),
    ]
    high = [
        make_span("2", 72, 300, 77, 306, size=6.0, superscript=True),
        make_span("Further details are given elsewhere.", 78, 300, 400, 312),
    ]
    pages = classify_pages(_doc(make_block(0, 0, [low]), make_block(0, 1, [high])))
    assert _type_of(pages, 0) == "footnote"
    assert _type_of(pages, 1) == "body"


def test_ing3_equation_by_low_prose_share() -> None:
    """A math-font block whose text-font letters are under EQ_PROSE_LETTERS is an equation
    (operands in CMR do not make it prose); a sentence with one math glyph stays body."""
    eq = [
        make_span("p", 200, 400, 205, 410, font="CMMI10"),
        make_span("(", 205, 400, 209, 410, font="CMR10"),
        make_span("y", 209, 400, 214, 410, font="CMMI10"),
        make_span(") = 1 + 2, (1)", 214, 400, 290, 410, font="CMR10"),
    ]
    prose = [
        make_span("the value of ", 72, 450, 140, 460, font="CMR10"),
        make_span("x", 140, 450, 145, 460, font="CMMI10"),
        make_span(" is positive in every case we tried", 145, 450, 330, 460, font="CMR10"),
    ]
    pages = classify_pages(_doc(make_block(0, 0, [eq]), make_block(0, 1, [prose])))
    assert _type_of(pages, 0) == "equation"
    assert _type_of(pages, 1) == "body"


def test_ing3_bare_equation_number_is_equation() -> None:
    pages = classify_pages(_doc(make_block(0, 0, ["(12)"], x0=500, y0=400)))
    assert _type_of(pages, 0) == "equation"


def test_ing3_table_region_wins_over_heading() -> None:
    """A bold header row inside a table region is table, not heading (tuned 2026-10-16)."""
    pages = classify_pages(
        _doc(
            make_block(0, 0, ["Model Accuracy Recall"], y0=310, bold=True),
            make_block(0, 1, ["Model Accuracy Recall"], y0=200, bold=True),
            table_bboxes=[BBox(72, 300, 540, 400)],
        )
    )
    assert _type_of(pages, 0) == "table"
    assert _type_of(pages, 1) == "heading"


def test_ing3_table_by_table_bbox_overlap() -> None:
    pages = classify_pages(
        _doc(
            make_block(0, 0, ["Alpha 12 Beta 13 Gamma 14"], y0=310),
            make_block(0, 1, ["Alpha 12 Beta 13 Gamma 14"], y0=200),
            table_bboxes=[BBox(72, 300, 540, 400)],
        )
    )
    assert _type_of(pages, 0) == "table"
    assert _type_of(pages, 1) == "body"


def test_ing3_equation_by_math_font_or_symbols() -> None:
    pages = classify_pages(
        _doc(
            make_block(0, 0, ["x + y = z"], y0=100, font="CMMI10"),
            make_block(0, 1, ["∑α≤β∫∂"], y0=150),
        )
    )
    assert _type_of(pages, 0) == "equation"
    assert _type_of(pages, 1) == "equation"


def test_ing3_list_items() -> None:
    pages = classify_pages(
        _doc(
            make_block(0, 0, ["1. First item in the list."], y0=100),
            make_block(0, 1, ["• Bullet item text here."], y0=150),
            make_block(0, 2, ["2) Second numbered item."], y0=200),
        )
    )
    assert [_type_of(pages, i) for i in range(3)] == ["list", "list", "list"]


def test_ing3_plain_text_is_body() -> None:
    pages = classify_pages(_doc())
    assert all(b.type == "body" for b in pages[0].blocks)


def _rotated(block: Block) -> Block:
    for ln in block.lines:
        ln.dir = (0.0, -1.0)
    return block


def test_ing3_rotated_margin_stamp_is_noise_but_rotated_figure_label_is_not() -> None:
    stamp = _rotated(make_block(0, 0, ["arXiv:2610.00001v1 [cs.CL] 14 Oct 2026"], x0=20, width=20))
    label = _rotated(make_block(0, 1, ["Accuracy (%)"], x0=300, width=10, y0=200))
    pages = classify_pages(_doc(stamp, label))
    assert _type_of(pages, 0) == "noise"
    assert _type_of(pages, 1) != "noise"


def test_ing3_single_page_running_header_in_top_band() -> None:
    pages = classify_pages(
        _doc(
            make_block(0, 0, ["NIST SP 800-207", "ZERO TRUST ARCHITECTURE"], y0=33, size=12),
            make_block(0, 1, ["Smaller running title"], y0=20, size=8),
            make_block(0, 2, ["Body text that starts high on the page."], y0=30, size=10),
        )
    )
    assert _type_of(pages, 0) == "header"
    assert _type_of(pages, 1) == "header"
    assert _type_of(pages, 2) == "body"


@pytest.mark.parametrize("text", ["ii", "PAGE i", "Page iv"])
def test_ing3_page_number_regex_matches_roman(text: str) -> None:
    assert PAGE_NUMBER_RE.match(text)


@pytest.mark.parametrize(
    "lines",
    [
        ["Preprint."],
        ["alice@uni.edu, bob@lab.org"],
        ["https://doi.org/10.6028/NIST.SP.800-207"],
        ["This publication is available free of charge from:"],
        ["C  O  M  P  U  T  E  R      S  E  C  U  R  I  T  Y"],
        ["____________________________"],
    ],
)
def test_ing3_boilerplate_lines_are_noise(lines: list[str]) -> None:
    assert _type_of(classify_pages(_doc(make_block(0, 0, lines, y0=300))), 0) == "noise"


def test_ing3_cover_signature_block_is_noise_only_low_on_cover_pages() -> None:
    low = make_block(0, 0, ["U.S. Department of Commerce"], y0=650)
    high = make_block(0, 1, ["Director of research"], y0=300)
    pages = classify_pages(_doc(low, high))
    assert _type_of(pages, 0) == "noise"
    assert _type_of(pages, 1) == "body"


def test_ing3_tiny_small_print_block_low_on_page_is_not_a_footnote() -> None:
    pages = classify_pages(
        _doc(
            make_block(0, 0, ["ij"], y0=700, size=7, width=8),
            make_block(0, 1, ["1 A real footnote text."], y0=720, size=7),
        )
    )
    assert _type_of(pages, 0) != "footnote"
    assert _type_of(pages, 1) == "footnote"


# --- D12: figure-internal text -------------------------------------------------------------

FIG = BBox(100, 100, 400, 300)  # a figure region on a 612 x 792 page


def _fig_doc(*extra: Block) -> list[Page]:
    blocks = list(extra) + _filler(0, len(extra))
    return [make_page(0, blocks, image_bboxes=[FIG], figure_bboxes=[FIG])]


def test_ing3_d12_block_inside_figure_region_is_figure() -> None:
    label = make_block(0, 0, ["Accuracy vs. tokens"], x0=150, width=150, y0=200)
    assert _type_of(classify_pages(_fig_doc(label)), 0) == "figure"


def test_ing3_d12_caption_inside_figure_region_stays_caption() -> None:
    cap = make_block(0, 0, ["Figure 1: Results on the benchmark."], x0=120, width=250, y0=280)
    assert _type_of(classify_pages(_fig_doc(cap)), 0) == "caption"


def test_ing3_d12_half_overlap_is_not_figure() -> None:
    # x 300-500: half of the block's width lies inside the region (x <= 400)
    half = make_block(0, 0, ["Ordinary body text beside a figure."], x0=300, width=200, y0=200)
    assert _type_of(classify_pages(_fig_doc(half)), 0) == "body"


def test_ing3_d12_figure_regions_union_and_area_bounds() -> None:
    from hearnarro.ingestion.extract import figure_regions

    w, h = 612.0, 792.0  # page area 484704; 2% = 9694
    # two overlapping rects (union 200 x 100 = 20000, ~4%) form one region
    a, b = BBox(100, 100, 200, 200), BBox(190, 100, 300, 200)
    # a small isolated box: 50 x 50 = 2500 (~0.5%) is ignored
    small = BBox(400, 500, 450, 550)
    # a page-background box (>= 80%) is ignored
    bg = BBox(0, 0, 612, 792)
    img = BBox(10, 600, 20, 610)  # images are regions whatever their size
    regions = figure_regions([img], [a, b, small], w, h)
    assert regions == [img, BBox(100, 100, 300, 200)]
    assert figure_regions([], [bg], w, h) == []
    assert figure_regions([], [small], w, h) == []
