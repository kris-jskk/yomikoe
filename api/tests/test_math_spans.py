"""MathSpan data from stage 1 to the reader (MATH-1, MATH-2; spec m5 §3a, D36, D37).

Every equation block carries one display span over its whole text; every inline maths fragment
stage 3 joins, and every maths-font run inside a body line, carries an inline span; and for every
span ``block.text[s.start:s.end]`` equals the joined text of ``s.runs`` up to whitespace.
"""

import json
from functools import cache
from pathlib import Path

import pytest

from tests.conftest import make_block, make_span
from yomikoe.ingestion.merge import merge_blocks, merge_lines, merge_lines_map
from yomikoe.ingestion.models import LogicalBlock
from yomikoe.ingestion.pipeline import IngestResult, ingest

FIXTURES = Path(__file__).parent / "fixtures" / "pdfs"
NAMES = sorted(e["name"] for e in json.loads((FIXTURES / "manifest.json").read_text()))


def _squash(text: str) -> str:
    return "".join(text.split())


def _violations(block: LogicalBlock) -> list[str]:
    out: list[str] = []
    for s in block.math_spans:
        got = _squash(block.text[s.start : s.end])
        # a content span (text-font maths found by content, m5 p3d) has no runs: no geometry
        want = _squash("".join(r.text for r in s.runs)) if s.runs else got
        if not (0 <= s.start < s.end <= len(block.text)) or got != want or not got:
            out.append(f"block {block.id} [{s.start}:{s.end}] {got!r} != {want!r}")
    return out


@cache
def _ingest(name: str) -> IngestResult:
    return ingest(FIXTURES / f"{name}.pdf", document_id=0, ocr=True)


def test_math2_merge_lines_map_matches_merge_lines() -> None:
    cases = [
        ["a  b ", "  c-", "dog", "X"],
        ["multi-", "Modal"],
        ["soft­", "ware", "", "   "],
    ]
    for lines in cases:
        for heading in (False, True):
            text, maps = merge_lines_map(lines, heading=heading)
            assert text == merge_lines(lines, heading=heading)
            for line, pos in zip(lines, maps, strict=True):
                for ch, p in zip(line, pos, strict=True):
                    if p >= 0:
                        assert text[p] == (" " if ch.isspace() else ch)


def test_math2_inline_run_in_a_body_line_is_spanned() -> None:
    line = [
        make_span("where ", 72, 100, 100, 112),
        make_span("x", 100, 100, 106, 112, font="CMMI10"),
        make_span("i", 106, 104, 109, 112, size=7.0, font="CMMI7"),
        make_span(" is the i-th sample.", 109, 100, 200, 112),
    ]
    (lb,) = merge_blocks([make_block(0, 0, [line])])
    (span,) = lb.math_spans
    assert lb.text[span.start : span.end] == "xi"
    assert not span.display and [r.text for r in span.runs] == ["x", "i"]


def test_math2_inline_fragment_joined_by_stage3_is_spanned() -> None:
    host = make_block(0, 0, ["and E[P"], x0=72, width=100, y0=100)
    frag = make_block(0, 1, ["i D(p, q)] = O(1)."], x0=172, width=80, y0=100, type="equation")
    frag.inline = True
    (lb,) = merge_blocks([host, frag])
    assert lb.text == "and E[P i D(p, q)] = O(1)."
    (span,) = lb.math_spans
    assert lb.text[span.start : span.end] == "i D(p, q)] = O(1)."
    assert not span.display and _violations(lb) == []


def test_math2_spans_survive_a_cross_page_join() -> None:
    a = make_block(0, 5, ["The loss is"], y0=700)
    b_line = [
        make_span("minimised over ", 72, 72, 150, 84),
        make_span("θ", 150, 72, 156, 84, font="CMMI10"),
        make_span(" here.", 156, 72, 190, 84),
    ]
    b = make_block(1, 0, [b_line])
    (lb,) = merge_blocks([a, b])
    (span,) = lb.math_spans
    assert lb.text[span.start : span.end] == "θ" and _violations(lb) == []


@pytest.mark.parametrize("name", NAMES)
def test_math1_math2_span_invariant_on_fixtures(name: str) -> None:
    result = _ingest(name)
    for b in result.blocks:
        if b.type == "equation" and b.text:
            assert len(b.math_spans) == 1, f"{name} block {b.id}: {len(b.math_spans)} spans"
            (s,) = b.math_spans
            assert (s.start, s.end, s.display) == (0, len(b.text), True), f"{name} {b.id}"
            assert not b.text.startswith("Equation"), f"{name} block {b.id}: cue in text"
    bad = [v for b in result.blocks for v in _violations(b)]
    assert bad == [], f"{name}: {bad[:5]}"
    counts = {
        "display": sum(s.display for b in result.blocks for s in b.math_spans),
        "inline": sum(not s.display for b in result.blocks for s in b.math_spans),
    }
    print(f"{name}\tdisplay={counts['display']}\tinline={counts['inline']}")
