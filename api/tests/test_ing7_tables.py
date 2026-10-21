"""Tables and equations as spoken cues (ING-7).

Spec: _agent/specs/m4-library-interfaces.md §3, rows "Tables" and "Equations". A table block's
rows are its lines and its cells are the spans of a line (cells sit far apart on the row). The
cue and row segments stay on blocks typed ``table`` so the D14 excluded-mass guard still sees
them as excluded. An equation block yields one segment; since MATH-1 (spec m5 §3b) its text is
the raw expression with one display MathSpan, and the "Equation N." cue is the reader's fallback.
"""

from tests.conftest import make_block, make_span
from yomikoe.ingestion.merge import merge_blocks
from yomikoe.ingestion.models import Block, LogicalBlock, Segment, Span
from yomikoe.ingestion.segment import split_sentences

CELL_X = (72.0, 232.0, 392.0)
CELL_W = 90.0
FILLER = "The results below summarize the survey across regions."
EQ_SYMBOLS = "∑∫≤≥=αβλ∂√^"


def _row(cells: list[str], top: float) -> list[Span]:
    return [
        make_span(text, CELL_X[i], top, CELL_X[i] + CELL_W, top + 12.0)
        for i, text in enumerate(cells)
    ]


def _table(page: int, index: int, rows: list[list[str]], y0: float = 200.0) -> Block:
    return make_block(
        page, index, [_row(r, y0 + 14.0 * i) for i, r in enumerate(rows)], type="table"
    )


def _segments(blocks: list[Block]) -> tuple[list[LogicalBlock], list[Segment]]:
    logical = merge_blocks(blocks)
    segments: list[Segment] = []
    for lb in logical:
        segments.extend(
            split_sentences(lb, document_id=0, order_start=len(segments), id_start=len(segments))
        )
    return logical, segments


def _texts(blocks: list[Block]) -> list[str]:
    return [s.text for s in _segments(blocks)[1]]


def test_ing7_table_cue_then_one_segment_per_row() -> None:
    table = _table(
        0, 0, [["Region", "Users", "Growth"], ["Europe", "1200", "4%"], ["Asia", "900", "7%"]]
    )
    assert _texts([table]) == [
        "Table 1, 3 rows.",
        "Region, Users, Growth.",
        "Europe, 1200, 4%.",
        "Asia, 900, 7%.",
    ]


def test_ing7_table_segments_stay_typed_table() -> None:
    """D14: cue and row segments belong to table blocks (excluded from prose comparison)."""
    table = _table(0, 0, [["Name", "Role"], ["Ada", "Analyst"]])
    logical, segments = _segments([table])
    types = {lb.id: lb.type for lb in logical}
    assert len(segments) == 3
    assert {types[s.block_id] for s in segments} == {"table"}


def test_ing7_table_rows_without_letters_are_skipped() -> None:
    table = _table(0, 0, [["Name", "Score"], ["1.0", "2.5"], ["Alice", "9"], ["--", "%"]])
    texts = _texts([table])
    assert texts[0].startswith("Table 1, ")
    assert "Name, Score." in texts
    assert "Alice, 9." in texts
    assert not any("1.0" in t or "2.5" in t or "--" in t for t in texts)
    assert len(texts) == 3


def test_ing7_tables_are_numbered_through_the_document() -> None:
    first = _table(0, 0, [["Year", "Total"], ["Twenty", "Ten"]])
    prose = make_block(0, 1, [FILLER], y0=400.0)
    second = _table(1, 0, [["Model", "Score"], ["Base", "High"]])
    texts = _texts([first, prose, second])
    cues = [t for t in texts if t.startswith("Table ")]
    assert cues == ["Table 1, 2 rows.", "Table 2, 2 rows."]
    assert texts.index("Table 2, 2 rows.") > texts.index(FILLER)


def test_ing7_math1_equation_block_is_one_segment_of_its_expression() -> None:
    # MATH-1 (spec m5 §3a, §3b): the equation block is still one segment, but its text is the
    # raw expression the mathspeak reader speaks; the "Equation." cue is the reader's fallback.
    eq = make_block(0, 0, ["∑ᵢ αᵢ xᵢ ≤ β", "λ = ∂f/∂x"], type="equation")
    logical, segments = _segments([eq])
    assert [s.text for s in segments] == ["∑ᵢ αᵢ xᵢ ≤ β λ = ∂f/∂x"]
    assert "Equation" not in logical[0].text
    assert logical[0].raw_text == logical[0].text  # D14 guard still weighs the expression
    (span,) = logical[0].math_spans
    assert (span.start, span.end, span.display, span.label) == (0, len(logical[0].text), True, None)


def test_ing7_math1_labelled_equation_keeps_its_number_as_label() -> None:
    # MATH-1, MATH-4: the trailing "(3)" stays in the text and becomes the span's label.
    eq = make_block(0, 0, ["f(x) = ∫ g(t) dt          (3)"], type="equation")
    logical, segments = _segments([eq])
    assert [s.text for s in segments] == ["f(x) = ∫ g(t) dt (3)"]
    assert logical[0].math_spans[0].label == "3"


def test_ing7_math1_equations_between_prose_stay_one_segment_each() -> None:
    blocks = [
        make_block(0, 0, [FILLER], y0=100.0),
        make_block(0, 1, ["x = √(a² + b²)          (12)"], y0=150.0, type="equation"),
        make_block(0, 2, ["∑ λᵢ ≥ 0"], y0=200.0, type="equation"),
        make_block(0, 3, [FILLER], y0=250.0),
    ]
    logical, segments = _segments(blocks)
    assert [s.text for s in segments] == [FILLER, "x = √(a² + b²) (12)", "∑ λᵢ ≥ 0", FILLER]
    assert [lb.type for lb in logical] == ["body", "equation", "equation", "body"]
    assert [[sp.label for sp in lb.math_spans] for lb in logical] == [[], ["12"], [None], []]
    for seg in (segments[0], segments[3]):
        assert not any(c in seg.text for c in EQ_SYMBOLS)
