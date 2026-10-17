"""Phase 3 noise rules (ING-4) and the U+FB00..U+FB06 ligatures (ING-5).

Spec: _agent/specs/m4-library-interfaces.md §3, rows "Page markers" and "Document 17 findings".
Pages are 612 x 792 pt; the header/footer bands are the top/bottom 8%, so every marker here sits
mid-page where the existing band rule does not reach it.
"""

import pytest

from hearnarro.ingestion.classify import classify_pages
from hearnarro.ingestion.extract import LayoutChar, ligature_text, page_from_layout
from hearnarro.ingestion.merge import merge_blocks
from hearnarro.ingestion.models import BBox, Block
from tests.conftest import make_block, make_page

FILLER = "This sentence is ordinary body text set in the document's main size."


def _filler(page: int, start_index: int) -> list[Block]:
    """Four long size-10 body blocks so the document median is 10."""
    return [
        make_block(page, start_index + i, [FILLER, FILLER], y0=100.0 + 60.0 * i) for i in range(4)
    ]


def _classified(marker: Block) -> Block:
    page = make_page(0, [*_filler(0, 0), marker])
    classify_pages([page])
    return marker


@pytest.mark.parametrize("text", ["[12]", "12", "[3]", "1024"])
def test_ing4_page_marker_mid_page_is_noise(text: str) -> None:
    """A block whose only text is a bracketed or bare number outside a TOC is noise."""
    marker = make_block(0, 4, [text], y0=400.0, width=30.0)
    assert _classified(marker).type == "noise"


def test_ing4_page_marker_between_paragraphs_is_noise() -> None:
    """ "[47]" left between two paragraphs by a scan-to-PDF tool (document 17) is dropped."""
    marker = make_block(0, 4, ["[47]"], x0=290.0, y0=360.0, width=32.0)
    assert _classified(marker).type == "noise"


@pytest.mark.parametrize("text", ["23", "147", "[9]"])
def test_ing4_heading_bare_page_number_is_noise(text: str) -> None:
    """TOC leakage: a heading-sized block whose text is a bare page number is noise."""
    marker = make_block(0, 4, [text], y0=420.0, width=40.0, size=16.0, bold=True)
    assert _classified(marker).type == "noise"


def test_ing4_heading_fragment_ending_in_hyphen_joins_next_line() -> None:
    """A heading line ending in a hyphen joins the next line of the same block, no space."""
    heading = make_block(0, 0, ["Multi-", "Modal Retrieval at Scale"], size=18.0, type="heading")
    (logical,) = merge_blocks([heading])
    assert logical.text == "Multi-Modal Retrieval at Scale"


def test_ing4_heading_hyphen_join_keeps_lowercase_rule() -> None:
    """The existing lowercase de-hyphenation still applies and the new rule adds no space."""
    heading = make_block(0, 0, ["Zero-", "Trust Archi-", "tecture"], size=18.0, type="heading")
    (logical,) = merge_blocks([heading])
    assert logical.text == "Zero-Trust Architecture"


# ---------------------------------------------------------------------------------------
# ING-5: U+FB00..U+FB06 decompose in stage 1
# ---------------------------------------------------------------------------------------

LIGATURES = {
    "ﬀ": "ff",
    "ﬁ": "fi",
    "ﬂ": "fl",
    "ﬃ": "ffi",
    "ﬄ": "ffl",
    "ﬅ": "st",
    "ﬆ": "st",
}


def _layout_line(text: str, x: float = 72.0, top: float = 100.0) -> list[LayoutChar]:
    out: list[LayoutChar] = []
    for ch in text:
        if ch == " ":
            out.append(LayoutChar(" ", None))
            x += 3.0
            continue
        out.append(LayoutChar(ch, BBox(x, top, x + 6.0, top + 10.0), "Times-Roman", 10.0))
        x += 6.0
    return out


@pytest.mark.parametrize(("char", "letters"), list(LIGATURES.items()))
def test_ing5_unicode_ligature_char_decomposes_in_stage1(char: str, letters: str) -> None:
    """A text-layer ligature code point becomes its letters in the stage 1 line text."""
    page = page_from_layout(0, 612.0, 792.0, [[_layout_line(f"e{char}ect of the change")]])
    text = page.blocks[0].text
    assert char not in text
    assert text == f"e{letters}ect of the change"


@pytest.mark.parametrize("code", ["FB05", "FB06"])
def test_ing5_uni_glyph_names_cover_fb05_fb06(code: str) -> None:
    """The glyph-name rule maps the two st ligatures like uniFB00..uniFB04."""
    assert ligature_text(f"uni{code}") == "st"
