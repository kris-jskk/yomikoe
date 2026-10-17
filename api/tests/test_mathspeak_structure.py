"""MATH-1, MATH-2, D37: expression trees from span geometry (spec §3b ``structure.parse``)."""

from __future__ import annotations

from hearnarro.ingestion.mathspeak.markup import markup_segment
from hearnarro.ingestion.mathspeak.structure import MathSpan, Node, parse
from hearnarro.ingestion.models import BBox, Span


def tree(raw: str) -> Node | None:
    text, (span,) = markup_segment(raw, "equation")
    return parse(span, text)


def kinds(node: Node | None) -> set[str]:
    if node is None:
        return set()
    out = {node.kind}
    for c in node.children:
        out |= kinds(c)
    return out


def test_math1_scripts_from_size_and_baseline() -> None:
    assert {"sup", "sub"} <= kinds(tree("x_{i}^{2}"))
    assert "sup" in kinds(tree("x²")) and "sub" in kinds(tree("xᵢ"))
    node = tree("x_{i}^{2}")
    assert node is not None and node.children[0] is not None
    assert node.children[0].kind == "sup" and node.children[0].children[0].kind == "sub"  # type: ignore[union-attr]


def test_math1_stacked_lines_are_a_fraction_with_the_prefix_outside() -> None:
    node = tree("x = a + b\nc")
    assert node is not None
    assert [c.kind for c in node.children if c] == ["var", "op", "frac"]


def test_math1_large_operators_take_limits() -> None:
    for raw, kind in (("∑_{i=1}^{n} x", "sum"), ("∏_{i=1}^{n} p", "prod"), ("∫_{a}^{b} f", "int")):
        node = tree(raw)
        assert node is not None
        op = node.children[0]
        assert op is not None and op.kind == kind and all(op.children)
    assert "limop" in kinds(tree("lim_{n→∞} a_{n}"))


def test_math1_root_group_apply_abs_norm() -> None:
    assert {"sqrt", "group"} <= kinds(tree("√(a + b)"))
    assert "apply" in kinds(tree("f(x)"))
    assert "abs" in kinds(tree("|x − y|")) and "norm" in kinds(tree("‖v‖"))


def test_math1_intervals_and_matrices() -> None:
    assert "interval" in kinds(tree("[0, 1]")) and "interval" in kinds(tree("(0, 1]"))
    assert "interval" in kinds(tree("x ∈ (0, 1)"))
    assert "interval" not in kinds(tree("k(x, y)")) and "interval" not in kinds(tree("(a, b)"))
    assert "matrix" in kinds(tree("[a b\nc d]"))


def test_math1_parse_returns_none_when_it_cannot_structure() -> None:
    assert tree("a ☃ b") is None  # an unknown character
    assert tree("(a + b") is None  # unbalanced bracket
    assert tree("a\nb\nc") is None  # three stacked rows that are not a matrix
    small = Span("2", BBox(0, 0, 4, 7), "CMMI10", 7.0, superscript=True)
    big = Span("x", BBox(5, 0, 10, 10), "CMMI10", 10.0)
    assert parse(MathSpan(0, 2, True, [small, big])) is None  # a script with no base


def test_math1_tree_json_round_trip() -> None:
    node = tree("∑_{i=1}^{n} x_{i}^{2}")
    assert node is not None and Node.from_json(node.to_json()) == node
