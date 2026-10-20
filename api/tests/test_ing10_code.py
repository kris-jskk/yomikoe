"""Code listings (ING-10; spec m5 §3d).

A block >= 70 % monospace by character, or of >= 3 lines with >= 50 % indented code lines, is
typed ``code``; table and caption rules still win; merge makes one LogicalBlock whose text is the
cue "Code listing, N lines." and whose raw_text keeps the code (D14 guard weighs it); inline
code inside prose is untouched.
"""

import json
from pathlib import Path

import pytest

from hearnarro.evals.scorers import PROSE_TYPES, excluded_actual_texts
from hearnarro.ingestion.classify import _classify, _is_code
from hearnarro.ingestion.merge import merge_blocks
from hearnarro.ingestion.models import Page
from hearnarro.ingestion.pipeline import ingest
from hearnarro.ingestion.segment import split_sentences
from tests.conftest import make_block, make_span

FIXTURES = Path(__file__).parent / "fixtures" / "pdfs"
CODE = [">>> def f(x):", "...     return x ** 2", ">>> f(3)", "9"]


def _page(*blocks):  # type: ignore[no-untyped-def]
    return Page(number=0, width=612.0, height=792.0, blocks=list(blocks))


def test_ing10_monospace_block_is_code() -> None:
    block = make_block(0, 0, CODE, font="LMMono10-Regular", y0=300)
    assert _classify(block, _page(block), 10.0, set(), []) == "code"


def test_ing10_inline_code_in_prose_stays_body() -> None:
    line = [
        make_span("Call ", 72, 300, 100, 312),
        make_span("sym.integrate", 100, 300, 170, 312, font="LMMono10-Regular"),
        make_span(" to integrate any expression you like in closed form.", 170, 300, 500, 312),
    ]
    block = make_block(0, 0, [line])
    assert not _is_code(block)
    assert _classify(block, _page(block), 10.0, set(), []) == "body"


def test_ing10_indented_punctuation_block_is_code() -> None:
    lines = [
        [make_span("int main() {", 72, 300, 200, 312)],
        [make_span("x = f(y);", 92, 314, 200, 326)],
        [make_span("return x;", 92, 328, 200, 340)],
        [make_span("}", 72, 342, 80, 354)],
    ]
    block = make_block(0, 0, lines)
    assert _classify(block, _page(block), 10.0, set(), []) == "code"


def test_ing10_listing_caption_still_wins() -> None:
    cap = make_block(0, 0, ["Listing 2: the training loop"], font="Courier", y0=300)
    page = _page(cap)
    page.image_bboxes = [make_block(0, 1, ["x"], y0=320).bbox]
    assert _classify(cap, page, 10.0, set(), []) == "caption"


def test_ing10_code_block_speaks_its_cue() -> None:
    block = make_block(0, 0, CODE, font="LMMono10-Regular", type="code")
    (lb,) = merge_blocks([block])
    assert lb.type == "code" and lb.text == "Code listing, 4 lines."
    assert lb.raw_text == "\n".join(CODE)
    (seg,) = split_sentences(lb, document_id=0, order_start=0, id_start=0)
    assert seg.text == "Code listing, 4 lines."
    assert seg.normalized_text.startswith("Code listing")
    assert len(seg.char_map) == len(seg.normalized_text)
    assert all(0 <= c < len(seg.text) for c in seg.char_map)
    assert seg.char_map == sorted(seg.char_map)


def test_ing10_d14_guard_weighs_code_raw_text() -> None:
    block = make_block(0, 0, CODE, font="LMMono10-Regular", type="code")
    logical = merge_blocks([block])
    segs = split_sentences(logical[0], document_id=0, order_start=0, id_start=0)
    assert "code" not in PROSE_TYPES
    excluded = excluded_actual_texts(logical, segs)
    assert len(excluded) == 1 and "return x ** 2" in excluded[0]


@pytest.mark.parametrize(
    "name",
    [
        "formula_08_sympy_integration",
        # m5 p3d: the near-full-page ruled region is prose between rules (is_prose_region)
        "formula_09_scipy_ode_oscillator",
    ],
)
def test_ing10_formula_fixtures_have_code_blocks(name: str) -> None:
    rows = [
        json.loads(x)
        for x in (FIXTURES / f"{name}.expected.jsonl").read_text().splitlines()
        if x.strip()
    ]
    expected = sum(r["type"] == "code" for r in rows)
    result = ingest(FIXTURES / f"{name}.pdf", document_id=0, ocr=True)
    code = [b for b in result.blocks if b.type == "code"]
    print(f"{name}\tcode blocks found={len(code)}\texpected={expected}")
    assert code, name
    for b in code:
        assert b.text.startswith("Code listing, ") and b.raw_text
