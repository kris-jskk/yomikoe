"""MATH-1, MATH-2, D37: expression trees from span geometry (spec §3b ``structure.parse``)."""

from __future__ import annotations

from yomikoe.ingestion.extract import LayoutChar, group_blocks, group_lines
from yomikoe.ingestion.mathspeak import speak_span
from yomikoe.ingestion.mathspeak.markup import markup_segment
from yomikoe.ingestion.mathspeak.structure import MathSpan, Node, parse
from yomikoe.ingestion.models import BBox, Span


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


# --- m5-p5i: residues of tables_04_markov_kernel.pdf (spec §8 Q9), geometry from results 1221 ---


def _glyphs(text: str, x: float, top: float, font: str, size: float) -> list[LayoutChar]:
    out: list[LayoutChar] = []
    for ch in text:
        if ch == " ":
            out.append(LayoutChar(" ", None))
            continue
        w = 0.5 * size
        out.append(LayoutChar(ch, BBox(x, top, x + w, top + size), font, size, True))
        x += w
    return out


def _text(line: list[LayoutChar]) -> str:
    return "".join(c.text for c in line).strip()


def test_math1_lone_sup_line_opens_the_display_block_with_its_condition() -> None:
    """MATH-1 (m5-p5i, equation (5)): a "sup" alone on its line under a prose line is not
    prose; its stacked condition and its operand stay in one display block."""
    prose = _glyphs("condition:", 82.8, 667.5, "SFRM1000", 9.96)
    op = _glyphs("sup", 206.3, 680.7, "CMR10", 9.96)
    cond = _glyphs("x∈X", 206.0, 691.5, "CMMI7", 6.97)
    body = _glyphs("MMD", 223.2, 680.7, "CMR10", 9.96) + _glyphs("ϕ", 238.2, 684.6, "CMMI7", 6.97)
    blocks = group_blocks([prose, op, cond, body])
    assert [[_text(ln) for ln in b] for b in blocks] == [["condition:"], ["sup", "x∈X", "MMDϕ"]]


def test_math1_hat_below_a_prose_word_starts_a_new_line() -> None:
    """ING-1/MATH-1 (m5-p5i, equation (2)): the CMEX hat of a display does not continue the
    prose line above it, so "surely," stays out of the display."""
    chars = [
        *_glyphs("surely,", 82.8, 605.3, "SFRM1000", 9.96),
        LayoutChar("b", BBox(149.8, 630.5, 155.3, 640.5), "CMEX10", 9.96, True),
        *_glyphs("µ", 149.8, 626.5, "CMMI10", 9.96),
    ]
    assert [_text(ln) for ln in group_lines(chars)] == ["surely,", "bµ"]


def _run(text: str, x0: float, y0: float, x1: float, font: str, size: float) -> Span:
    return Span(text, BBox(x0, y0, x1, y0 + size), font, size)


def _speak_runs(runs: list[Span]) -> str:
    text = " ".join(r.text for r in runs)
    spoken, _ = speak_span(MathSpan(0, len(text), True, runs), text)
    return spoken


def test_math1_sup_with_its_condition_below_reads_the_supremum_over() -> None:
    """MATH-1 (m5-p5i, equation (5)): the condition under "sup" is its limit, never a
    fraction numerator; the operand runs to the relation."""
    runs = [
        _run("sup", 206.3, 680.7, 221.3, "CMR10", 9.96),
        _run("x", 206.0, 691.5, 210.5, "CMMI7", 6.97),
        _run("∈", 210.5, 691.5, 215.9, "CMSY7", 6.97),
        _run("X", 216.1, 691.7, 222.3, "CMSY7", 6.97),
        _run("f", 223.2, 680.7, 228.0, "CMMI10", 9.96),
        _run("(", 228.4, 680.7, 232.3, "CMR10", 9.96),
        _run("x", 232.3, 680.7, 238.0, "CMMI10", 9.96),
        _run(")", 238.2, 680.7, 242.1, "CMR10", 9.96),
        _run("≤", 245.2, 680.7, 253.0, "CMSY10", 9.96),
        _run("1", 256.0, 680.7, 261.0, "CMR10", 9.96),
    ]
    spoken = _speak_runs(runs)
    assert spoken.startswith("the supremum over x in x of f of x")
    assert "fraction" not in spoken and "is less than or equal to 1" in spoken


def test_math1_one_subscript_in_several_runs_is_one_script() -> None:
    """MATH-1 (m5-p5i, equation (8)): "L2(H)" set as five subscript runs reads as one
    subscript, never a chain of "sub sub"."""
    runs = [
        _run("A", 201.7, 260.8, 208.9, "CMMI10", 9.96),
        _run("L", 210.0, 266.2, 216.6, "CMSY7", 6.97),
        _run("(", 216.8, 266.2, 219.9, "CMR7", 6.97),
        _run("H", 220.0, 266.2, 226.9, "CMSY7", 6.97),
        _run(")", 226.9, 266.2, 230.0, "CMR7", 6.97),
        _run("=", 233.0, 260.8, 240.8, "CMR10", 9.96),
        _run("b", 243.0, 260.8, 248.0, "CMMI10", 9.96),
    ]
    spoken = _speak_runs(runs)
    assert "sub sub" not in spoken
    assert spoken == "a sub l of h equals b"
