"""ING-6 / MATH-1 fallback: mathematical symbols and Greek letters are read by name, left to right.

PRD MATH-1 fallback clause: "the symbols left to right by name, never silence and never symbol
soup". Structured maths (sub/superscripts, fractions, exponents, absolute values, display
equations) is NOT handled here; it is M5 MATH-1 / MATH-2 proper. The twelve real cases come from
the Navier-Stokes paper audit (``_agent/results/637_navier_math_audit.md`` section 2; fixture use
permitted by the user). Their expected texts below are what the fallback produces and keep the
structural parts deliberately wrong: digits stay digits ("0", misaki reads "zero"), "R3" / "t1"
stay glued (superscript or subscript lost in extraction), "1/2" and "X−1/2−h" are read as plain
operators (exponent lost), "1 2" for one half and "|u|2" are left as extracted, "ur" / "uz" stay
as written, and intervals keep their brackets.
"""

from itertools import pairwise

import pytest

from hearnarro.ingestion.math_symbols import GREEK, LETTER_NAMES, SYMBOL_NAMES
from hearnarro.ingestion.normalize import normalize


def _check_map(text: str, out: str, cmap: list[int]) -> None:
    assert len(cmap) == len(out)
    assert all(0 <= i < len(text) for i in cmap)
    assert all(a <= b for a, b in pairwise(cmap))


@pytest.mark.parametrize(("sym", "name"), sorted(SYMBOL_NAMES.items()))
def test_math1_symbol_spaced_read_by_name(sym: str, name: str) -> None:
    text = f"a {sym} b"
    out, cmap = normalize(text)
    assert out == f"a {name} b"
    _check_map(text, out, cmap)
    o = out.index(name)
    assert set(cmap[o : o + len(name)]) == {2}  # every char of the name points at the symbol


@pytest.mark.parametrize(("sym", "name"), sorted(SYMBOL_NAMES.items()))
def test_math1_symbol_glued_separated_by_spaces(sym: str, name: str) -> None:
    text = f"x{sym}y"
    out, cmap = normalize(text)
    assert out == f"x {name} y"
    _check_map(text, out, cmap)
    assert set(cmap[1:-1]) == {1}


@pytest.mark.parametrize(("sym", "letter"), sorted(LETTER_NAMES.items()))
def test_math1_blackboard_bold_is_a_letter(sym: str, letter: str) -> None:
    out, cmap = normalize(f"x in {sym}3")
    assert out == f"x in {letter}3"
    assert cmap == list(range(len(out)))


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("for ν > 0", "for nu greater than 0"),
        ("if x>0 then", "if x greater than 0 then"),
        ("times t1<t2", "times t1 less than t2"),
        ("a < b", "a less than b"),
        ("supp u(·, t)", "supp u of (dot, t)"),
        ("a·b", "a dot b"),
        ("a ⋅ b", "a dot b"),
        ("x − y", "x minus y"),
        ("x−1", "x minus 1"),
        ("uθ and Kν", "u theta and K nu"),
        ("C∞ and c∞X", "C infinity and c infinity X"),
        ("X →∞", "X goes to infinity"),
        ("αβ", "alpha beta"),
        ("Σ and Δ", "sigma and delta"),
        ("∫︁ R3 and (︁1", "integral R3 and (1"),
        ("f ∈(0, 1)", "f in (0, 1)"),
    ],
)
def test_math1_context_and_spacing(text: str, expected: str) -> None:
    out, cmap = normalize(text)
    assert out == expected
    _check_map(text, out, cmap)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("f = O(1)", "f equals O of (1)"),  # a line-leading "=" is not read (pass one)
        ("E(X, η)", "E of (X, eta)"),
        ("u(x, t)", "u of (x, t)"),
        ("O(X−1)", "O of (X minus 1)"),
        (
            "with E(X, η) = O(1) as X → ∞.",
            "with E of (X, eta) equals O of (1) as X goes to infinity.",
        ),
        ("f(η(x))", "f of (eta of (x))"),
        ("[g(x)]", "[g of (x)]"),
        ("cost O(n log n)", "cost O of (n log n)"),
    ],
)
def test_math1_function_application_of(text: str, expected: str) -> None:
    """MATH-1 fallback / MATH-2 (ClearSpeak "f of x"): a lone letter glued to "(" is applied."""
    out, cmap = normalize(text)
    assert out == expected
    _check_map(text, out, cmap)
    assert "  " not in out


@pytest.mark.parametrize(
    "text",
    [
        "the word(s) here",
        "see Table(s) 2",
        "log(x)",
        "item 2(a)",
        "a (b)",
        "E (1)",
        "uθ(x)",
        "2x(y)",
    ],
)
def test_math1_function_application_negatives(text: str) -> None:
    out, cmap = normalize(text)
    assert " of " not in out
    _check_map(text, out, cmap)


def test_math1_function_application_maps_of_to_letter() -> None:
    text = "E(X)"
    out, cmap = normalize(text)
    assert out == "E of (X)"
    assert cmap[: len("E of ")] == [0] * len("E of ")


def test_math1_every_greek_letter_named() -> None:
    assert len({c for c in GREEK if c != "ℓ"}) == 2 * 24 + 6


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("see <https://example.org>", None),
        ("a -> b", "a -> b"),
        ("a => b", "a => b"),
        ("x <= y", "x <= y"),
        ("x >= y", "x >= y"),
        ("a << b and c >> d", "a << b and c >> d"),
        ("<div>", "<div>"),
        ("<h1>Title</h1>", "<h1>Title</h1>"),
        ("I <3 you", "I <3 you"),
        ("the 3 × 4 m room", "the 3 times 4 m room"),
        ("Home · About", "Home · About"),
        ("H = −∑ p", "H equals minus sum p"),  # after "equals", a word operand
        ("a 5 µm cell", "a 5 µm cell"),
        ("the word λόγος", "the word λόγος"),
    ],
)
def test_math1_prose_guards(text: str, expected: str | None) -> None:
    out, cmap = normalize(text)
    _check_map(text, out, cmap)
    if expected is None:
        assert "than" not in out and "<" in out and ">" in out
    else:
        assert out == expected


def test_math1_angle_bracket_email_untouched() -> None:
    out, _ = normalize("write to <name@host.com> today")
    assert "than" not in out and out.startswith("write to <") and "> today" in out


CASES = [
    (
        242,
        (
            "For every ν > 0 there exist a force f ∈C∞ c (R3 × (0, ∞); R3), a compact set K ⊂R3, "
            "and smooth velocity and pressure fields u, p on R3 × [0, 1) satisfying"
        ),
        (
            "For every nu greater than 0 there exist a force f in C infinity c (R3 times (0, "
            "infinity); R3), a compact set K subset of R3, and smooth velocity and pressure fields "
            "u, p on R3 times [0, 1) satisfying"
        ),
    ),
    (
        244,
        "such that supp u(·, t) ∪ supp p(·, t) ⊂K for every 0 ≤t < 1,",
        (
            "such that supp u of (dot, t) union supp p of (dot, t) subset of K for every 0 less "
            "than or equal to t less than 1,"
        ),
    ),
    (
        316,
        "The central part of the inner core at successive times t1 < t2 < t3 < 1.",
        (
            "The central part of the inner core at successive times t1 less than t2 less than t3 "
            "less than 1."
        ),
    ),
    (
        302,
        (
            "The velocity components ur, uθ, and uz describe motion toward or away from the axis, "
            "around the axis, and along it, respectively."
        ),
        (
            "The velocity components ur, u theta, and uz describe motion toward or away from the "
            "axis, around the axis, and along it, respectively."
        ),
    ),
    (
        580,
        "Here a ∈R3 is a constant amplitude, ξ ∈R3 is the wavevector, and φ ∈R is a phase.",
        (
            "Here a in R3 is a constant amplitude, xi in R3 is the wavevector, and phi in R is a "
            "phase."
        ),
    ),
    (
        473,
        (
            "Outside a fixed radial interval in X, U = V0 = 0, while E(X, η) = "
            "c∞X−1/2−h(︁1 + O(X−1))︁ (X →∞), c∞ > 0,"
        ),
        (
            "Outside a fixed radial interval in X, U equals V0 equals 0, while E of (X, eta) "
            "equals c infinity X minus 1/2 minus h(1 + O of (X minus 1)) (X goes to infinity), c "
            "infinity greater than 0,"
        ),
    ),
    (
        248,
        (
            "Consequently, there is no smooth solution (u, P) on R3 × [0, ∞) with the same force "
            "and initial datum whose kinetic energy is uniformly bounded supt≥0 1 2 ∫︁ R3 "
            "|u(x, t)|2 dx < ∞."
        ),
        (
            "Consequently, there is no smooth solution (u, P) on R3 times [0, infinity) with the "
            "same force and initial datum whose kinetic energy is uniformly bounded supt greater "
            "than or equal to 0 1 2 integral R3 |u(x, t)|2 dx less than infinity."
        ),
    ),
    (243, "Equation.", "Equation."),
    (241, "Theorem 1.1.", "Theorem 1.1."),
    (
        258,
        (
            "The first equation in (1.2) says that this acceleration is related by Newton’s second "
            "law to the sum of the negative pressure gradient and the external force."
        ),
        (
            "The first equation in (1.2) says that this acceleration is related by Newton’s second "
            "law to the sum of the negative pressure gradient and the external force."
        ),
    ),
    (
        5528,
        (
            "Thus the force remains smooth and compactly supported in Kν × [0, 2], and satisfies "
            "all required decay bounds for each fixed ν > 0."
        ),
        (
            "Thus the force remains smooth and compactly supported in K nu times [0, 2], and "
            "satisfies all required decay bounds for each fixed nu greater than 0."
        ),
    ),
    (
        325,
        (
            "Both lengths tend to zero, while ℓr/ℓz ≍ τh →0: the core becomes an increasingly "
            "slender column concentrated at the origin, with volume of order τ3/2−h."
        ),
        (
            "Both lengths tend to zero, while ell r/ell z asymptotically equal to tau h goes to 0: "
            "the core becomes an increasingly slender column concentrated at the origin, with "
            "volume of order tau 3/2 minus h."
        ),
    ),
]


@pytest.mark.parametrize(("seg", "raw", "expected"), CASES, ids=[str(c[0]) for c in CASES])
def test_math1_navier_segments(seg: int, raw: str, expected: str) -> None:
    out, cmap = normalize(raw)
    assert out == expected
    _check_map(raw, out, cmap)
    assert "  " not in out
