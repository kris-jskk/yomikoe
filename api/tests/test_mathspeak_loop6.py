"""M5 phase 3 loop 6: drawn fraction bars and radicals in text fonts, three-level TeX displays
with a relation in the numerator run, and large-operator limits (MATH-1..3, ING-3, gate b)."""

from __future__ import annotations

from hearnarro.ingestion.extract import LayoutChar, group_lines, vector_maths
from hearnarro.ingestion.mathspeak import reader, structure
from hearnarro.ingestion.mathspeak.structure import MathSpan
from hearnarro.ingestion.models import BBox, Span

IT, UP = "STIXGeneral-Italic", "STIXGeneral-Regular"


def _c(text: str, x0: float, x1: float, top: float, font: str = IT, size: float = 10.0):
    return LayoutChar(text, BBox(x0, top, x1, top + size), font, size, True)


def _speak(text: str) -> str:
    node = structure.parse(MathSpan(0, len(text), False, []), text, partial=True)
    assert node is not None
    return " ".join(reader.speak(node).split())


# fixture 06's "s = sqrt(Σ(x − x̄)² / (n − 1))": bar at 465.9, radical overline at 446.7
_06 = [
    _c("s", 94.0, 97.9, 461.5),
    _c("=", 100.7, 107.5, 462.9, UP),
    _c("Σ", 116.0, 122.2, 456.2),
    _c("(", 122.6, 125.9, 457.6, UP),
    _c("x", 126.2, 130.6, 456.2),
    _c("−", 132.8, 139.7, 457.6, UP),
    _c("x", 144.2, 148.7, 456.2),
    _c("¯", 144.7, 148.0, 453.2, UP),
    _c(")", 150.8, 154.1, 457.6, UP),
    _c("2", 154.8, 158.8, 449.3, UP, 8.0),
    _c("n", 126.7, 131.7, 467.3),
    _c("−", 133.9, 140.0, 468.7, UP),
    _c("1", 141.0, 148.0, 468.7, UP),
    _c("o", 163.8, 167.7, 461.0, "LiberationSerif", 9.5),
    _c("r", 167.7, 171.7, 461.0, "LiberationSerif", 9.5),
]
_06_STROKES = [
    BBox(115.3, 465.9, 159.4, 465.9),  # fraction bar
    BBox(110.8, 455.0, 111.7, 460.6),  # radical tick
    BBox(111.7, 455.0, 113.0, 474.4),
    BBox(113.0, 446.7, 115.3, 474.4),  # rising stroke, meets the overline's left end
    BBox(115.3, 446.7, 159.9, 446.7),  # overline
]


def test_math1_vector_radical_over_fraction_is_one_linear_run() -> None:
    out = vector_maths(_06, _06_STROKES)
    text = "".join(c.text for c in out)
    assert text == "s=√(∑(x−x¯)²)⁄(n−1)or"
    lines = group_lines(out)
    assert len(lines) == 1  # stage 1 no longer splits it over three lines


def test_math1_vector_fraction_spoken() -> None:
    assert _speak("s = √(∑(x−x¯)²)⁄(n−1)") == (
        "s equals the square root of the fraction the sum of x minus x bar, squared over n minus"
        " 1, end fraction"
    )
    assert _speak("μ = (nr)⁄(r+b)") == "mu equals the fraction n r over r plus b, end fraction"
    assert _speak("(1)⁄(p)") == "1 over p"


def test_math1_vector_construct_needs_slanted_root_and_centred_parts() -> None:
    # a vertical box edge meeting a rule is not a radical; a rule under prose is not a bar
    box = [BBox(113.0, 446.7, 113.0, 474.4), BBox(113.0, 446.7, 159.9, 446.7)]
    assert vector_maths(_06, box) == _06[:]
    prose = [
        _c(ch, 100 + 5 * i, 104 + 5 * i, 100.0, "LiberationSerif") for i, ch in enumerate("ab")
    ]
    nxt = [
        _c(ch, 100 + 5 * i, 104 + 5 * i, 112.0, "LiberationSerif") for i, ch in enumerate("cdefgh")
    ]
    assert vector_maths(prose + nxt, [BBox(100.0, 110.5, 109.0, 110.5)]) == prose + nxt


def test_math1_vector_skips_tex_math_fonts() -> None:
    tex = [_c("a", 100, 105, 90.0, "CMMI10"), _c("b", 100, 105, 102.0, "CMMI10")]
    assert vector_maths(tex, [BBox(99.0, 100.5, 106.0, 100.5)]) == tex


def _run(text: str, font: str, size: float, x0: float, x1: float, y0: float, y1: float) -> Span:
    return Span(text, BBox(x0, y0, x1, y1), font, size, False, False, False)


def test_math2_three_level_display_relation_run_and_sum_limits() -> None:
    # fixture 03 equation 11: mu-hat_T := (1/T) sum_{t=0}^{T-1} delta_{X_t}
    runs = [
        _run("µ", "CMMI10", 10.0, 261.6, 267.7, 175.0, 185.0),
        _run("T ", "CMMI7", 7.0, 267.6, 272.4, 178.9, 185.9),
        _run(":= 1 ", "CMR10", 10.0, 276.7, 297.3, 168.3, 185.0),
        _run("T ", "CMMI10", 10.0, 291.2, 297.0, 181.9, 191.8),
        _run("T ", "CMMI7", 7.0, 301.2, 305.9, 165.0, 172.0),
        _run("−", "CMSY7", 7.0, 307.0, 313.2, 165.0, 172.0),
        _run("1", "CMR7", 7.0, 313.2, 317.2, 165.0, 172.0),
        _run("X", "CMEX10", 10.0, 302.0, 316.4, 169.6, 179.6),
        _run("t", "CMMI7", 7.0, 302.7, 305.7, 189.1, 196.1),
        _run("=0", "CMR7", 7.0, 305.7, 315.8, 189.1, 196.1),
        _run("δ", "CMMI10", 10.0, 318.9, 323.3, 175.0, 185.0),
    ]
    node = structure.parse(MathSpan(0, 20, True, runs), partial=True)
    assert node is not None
    spoken = " ".join(reader.speak(node).split())
    assert "is defined as 1 over t the sum from t equals 0 to t minus 1 of delta" in spoken


def test_ing3_table_rule_between_header_and_body_is_not_a_fraction() -> None:
    head = [
        _c(ch, 100 + 5 * i, 104 + 5 * i, 100.0, "LiberationSans") for i, ch in enumerate("Type")
    ]
    body = [
        _c(ch, 100 + 5 * i, 104 + 5 * i, 112.0, "LiberationSans") for i, ch in enumerate("Qwen")
    ]
    assert vector_maths(head + body, [BBox(99.0, 111.0, 120.0, 111.0)]) == head + body
