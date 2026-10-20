"""M5 phase 3 loop 7: fixture 08 (unicode-math text layer in list items): list items keep their
maths-font runs, mathematical alphanumerics lex as plain letters (𝑙𝑜𝑔 is log), and a text-font
limit operator joins its subscript and the function word after it (MATH-1..3, MATH-2, gate b)."""

from __future__ import annotations

from hearnarro.ingestion import mathspeak as ms
from hearnarro.ingestion.mathspeak import reader, structure
from hearnarro.ingestion.mathspeak.structure import MathSpan
from hearnarro.ingestion.merge import _item_lines
from hearnarro.ingestion.models import BBox, Span

MI, MI7, SY7, RM7 = (
    "LMMathItalic10-Regular",
    "LMMathItalic7-Regular",
    "LMMathSymbols7-Regular",
    "LMRoman7-Regular",
)


def _run(text: str, x0: float, top: float, font: str = MI, size: float = 10.0) -> Span:
    return Span(text, BBox(x0, top, x0 + 5.0 * len(text), top + size), font, size)


def _say(text: str, spans: list[MathSpan]) -> str:
    local = ms.coalesce_spans(text, spans)
    local = ms.join_spans(text, [*local, *ms.glyph_spans(text, local)])
    return " ".join(ms._speak(text, local, None)[0].split())


def test_math_italic_letters_lex_as_plain_letters_math_1() -> None:
    assert [t.text for t in structure._lex("𝑙𝑜𝑔(𝑥)")][:1] == ["log"]
    node = structure.parse(MathSpan(0, 6, False, []), "𝑙𝑜𝑔(𝑥)")
    assert node is not None
    assert " ".join(reader.speak(node).split()) == "log of x"


def test_math_italic_product_stays_letters_math_1() -> None:
    # in a maths font juxtaposed italic letters that spell no function word are a product
    node = structure.parse(MathSpan(0, 3, False, [_run("𝑎𝑏𝑐", 100.0, 100.0)]), "𝑎𝑏𝑐")
    assert node is not None
    assert " ".join(reader.speak(node).split()) == "a b c"


def test_text_font_function_word_is_a_maths_gap_math_2() -> None:
    assert ms._maths_gap(" sin(")
    assert not ms._maths_gap(" and (")


def test_text_font_limit_reads_its_subscript_as_the_limit_math_1() -> None:
    # fixture 08 item 1: "lim" (LMRoman10), 𝑥→0 at 7 pt, "sin(" (LMRoman10), 𝑥, ")", "/𝑥"
    text = "Calculate lim𝑥→0 sin(𝑥)/𝑥"
    spans = [
        MathSpan(
            13,
            17,
            False,
            [
                _run("𝑥", 160.5, 165.3, MI7, 7.0),
                _run("→", 165.0, 165.3, SY7, 7.0),
                _run("0 ", 172.9, 165.3, RM7, 7.0),
            ],
        ),
        MathSpan(21, 22, False, [_run("𝑥", 195.2, 161.4)]),
        MathSpan(23, 25, False, [_run("/𝑥", 204.8, 161.4)]),
    ]
    assert _say(text, spans) == "Calculate the limit as x approaches 0 of sine of x over x"


def test_list_items_of_whole_lines_map_to_their_lines_math_2() -> None:
    lines = ["1. Calculate lim𝑥→0 sin(𝑥)/𝑥", "2. Calculate the derivative of", "𝑙𝑜𝑔(𝑥) for 𝑥."]
    assert _item_lines(lines) == [[0], [1, 2]]
    assert _item_lines(["→ a → b"]) is None  # a line split before an inline glyph item
