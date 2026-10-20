"""Stage 5 normalization for speech with char_map (subset of ING-6)."""

from itertools import pairwise

import pytest

from hearnarro.ingestion.normalize import normalize

VARIED = [
    "The cat sat on the mat.",
    "As shown in [12], the effect is real.",
    "Prior work [3, 4] and [12–14] disagrees.",
    "Smith et al. found 3.2% growth.",
    "See https://arxiv.org/abs/1706.03762 for details.",
    "Visit www.example.com/page today.",
    "Export the PDF and send it to NASA.",
    "",
    "An HTML page, a CSV file, and the GPU.",
    "Rates rose 12% then 0.5% [7] in the EU.",
    "Co-founded Vast.com and went public as part of Shopping.com.",
    "Write to corporate@oreilly.com or see https://angel.co/syndicates/ now.",
    "Go to http:// www.killingbuddha.co/blog/2016/2/19/naval (or Twitter.com/Naval).",
]


@pytest.mark.parametrize("text", VARIED)
def test_ing6_char_map_invariants(text: str) -> None:
    out, cmap = normalize(text)
    assert len(cmap) == len(out)
    assert all(0 <= i < len(text) for i in cmap)
    assert all(a <= b for a, b in pairwise(cmap))


@pytest.mark.parametrize(
    "text", ["The cat sat on the mat.", "It rained, and then it stopped; nobody minded."]
)
def test_ing6_identity_on_plain_prose(text: str) -> None:
    assert normalize(text) == (text, list(range(len(text))))


def _assert_expansion_in_span(text: str, token: str, out: str, cmap: list[int], exp: str) -> None:
    start = text.index(token)
    end = start + len(token)
    o = out.index(exp)
    mapped = cmap[o : o + len(exp)]
    assert all(start <= i < end for i in mapped), mapped
    assert mapped[0] == start
    assert mapped[-1] == end - 1


def test_ing6_citation_dropped_and_space_collapsed() -> None:
    text = "as shown [12] here"
    out, cmap = normalize(text)
    assert out == "as shown here"
    assert cmap[:8] == list(range(8))
    assert text[cmap[8]] == " "
    assert cmap[9:] == [14, 15, 16, 17]


def test_ing6_citation_list_and_range_dropped() -> None:
    assert normalize("prior work [3, 4] disagrees")[0] == "prior work disagrees"
    assert normalize("prior work [12–14] disagrees")[0] == "prior work disagrees"


def test_ing6_consecutive_drops_collapse_to_one_space() -> None:
    text = "word [1] [2] next"
    out, cmap = normalize(text)
    assert out == "word next"
    assert text[cmap[4]] == " "


def test_ing6_et_al() -> None:
    out, cmap = normalize("Smith et al. found")
    assert out == "Smith et al found"
    assert cmap[:11] == list(range(11))


def test_ing6_percent() -> None:
    text = "growth of 3.2% today"
    out, cmap = normalize(text)
    assert out == "growth of 3.2 percent today"
    _assert_expansion_in_span(text, "3.2%", out, cmap, "3.2 percent")
    assert cmap[out.index(" today")] == text.index(" today")


def test_ing6_url_to_domain() -> None:
    text = "see https://arxiv.org/abs/1 now"
    out, cmap = normalize(text)
    assert out == "see arxiv dot org slash abs slash 1 now"
    url = "https://arxiv.org/abs/1"
    start = text.index(url)
    o = out.index("arxiv")
    assert all(start <= i < start + len(url) for i in cmap[o : o + len("arxiv dot org")])


def test_ing6_www_url_keeps_host_and_short_path() -> None:
    out, _ = normalize("Visit www.example.com/page today.")
    assert out == "Visit example dot com slash page today."


@pytest.mark.parametrize("text", ["open the PDF file", "ask NASA today", "a TED talk by the CEO"])
def test_ing6_all_caps_tokens_left_for_the_backend(text: str) -> None:
    """Acronym pronunciation is decided in the synthesis backend (SYN-4), not here."""
    assert normalize(text) == (text, list(range(len(text))))


# --- domains, web addresses and e-mail spoken as read (ING-6) ---


def _assert_dot_maps_to_dot(text: str, out: str, cmap: list[int]) -> None:
    """Every char of each spoken " dot " / " slash " / " at " maps onto one source . / @."""
    for word, src in ((" dot ", "."), (" slash ", "/"), (" at ", "@")):
        if src not in text:
            continue
        o = out.find(word)
        while o != -1:
            mapped = set(cmap[o : o + len(word)])
            assert len(mapped) == 1, (word, mapped)
            assert text[mapped.pop()] == src
            o = out.find(word, o + 1)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("part of shopping.com today", "part of shopping dot com today"),
        ("he co-founded vast.com and", "he co-founded vast dot com and"),
        ("Go to Navalmanack.com to get", "Go to Navalmanack dot com to get"),
        ("see https://angel.co/syndicates now", "see angel dot co slash syndicates now"),
        ("join at www.ericpartaker.com today", "join at ericpartaker dot com today"),
        ("titles (http://safaribooksonline.com).", "titles (safaribooksonline dot com)."),
        ("see vast.com.", "see vast dot com."),
        ("the site (shopping.com) works", "the site (shopping dot com) works"),
        ("On Twitter: Twitter.com/Naval.", "On Twitter: Twitter dot com slash Naval."),
        ("at news.bbc.co.uk now", "at news dot bbc dot co dot uk now"),
        ("https:// startupboy.com/2011/12/13/why-you-cant-hire/.", "startupboy dot com."),
        ("my blog at www. ericpartaker.com, but", "my blog at ericpartaker dot com, but"),
    ],
)
def test_ing6_domain_spoken_with_dot(text: str, expected: str) -> None:
    out, cmap = normalize(text)
    assert out == expected
    assert len(cmap) == len(out)
    assert all(0 <= i < len(text) for i in cmap)
    assert all(a <= b for a, b in pairwise(cmap))
    _assert_dot_maps_to_dot(text, out, cmap)


def test_ing6_domain_char_map_points_at_source_letters() -> None:
    text = "part of shopping.com today"
    out, cmap = normalize(text)
    for word in ("shopping", "com", "today"):
        o, i = out.index(word), text.index(word)
        assert cmap[o : o + len(word)] == list(range(i, i + len(word)))


def test_ing6_www_maps_to_nothing() -> None:
    text = "at www.ericpartaker.com now"
    out, cmap = normalize(text)
    assert out == "at ericpartaker dot com now"
    assert cmap[out.index("ericpartaker")] == text.index("ericpartaker")


def test_ing6_long_path_dropped() -> None:
    out, _ = normalize("see https://www.forbes.com/sites/petercohan/2012/02/06/x now")
    assert out == "see forbes dot com now"


def test_ing6_email_spoken_with_at_and_dot() -> None:
    text = "contact corporate@oreilly.com."
    out, cmap = normalize(text)
    assert out == "contact corporate at oreilly dot com."
    _assert_dot_maps_to_dot(text, out, cmap)
    assert all(a <= b for a, b in pairwise(cmap))


@pytest.mark.parametrize(
    "text",
    [
        "Use n.b. a cat.",  # "e.g." is expanded by TERM-4 (test_term4_abbreviations.py)
        "growth of 3.2 units",
        "See Fig.2 below.",
        "release v1.2.3 shipped",
        "on Twitter @Naval today",
        "the end.So we left",
        "an e-commerce site",
        "Visit Nav.al for more",
    ],
)
def test_ing6_non_domains_untouched(text: str) -> None:
    assert normalize(text) == (text, list(range(len(text))))


GLYPH_ITEMS = [f"{g} Item text here" for g in "•·▪▫■□●○◦‣►▶➢➤→⇒✓✔✗✘★☆-–*"]


@pytest.mark.parametrize("text", [*GLYPH_ITEMS, "→Tight item", "  →  Spaced item", "→"])
def test_ing6_leading_bullet_glyph_is_silent(text: str) -> None:
    out, cmap = normalize(text)
    body = text.lstrip().lstrip("•·▪▫■□●○◦‣►▶➢➤→⇒✓✔✗✘★☆-–*").lstrip()
    assert out == body
    assert len(cmap) == len(out)
    assert all(0 <= i < len(text) for i in cmap)
    assert all(a <= b for a, b in pairwise(cmap))
    assert all(text[i] == ch for i, ch in zip(cmap, out, strict=True))


@pytest.mark.parametrize(
    "text",
    ["1. First step", "a) Second", "(3) Third", "-based storage", "*emphasis*", "— Wired"],
)
def test_ing6_numbered_markers_and_non_bullets_are_spoken(text: str) -> None:
    out, cmap = normalize(text)
    assert out == text
    assert cmap == list(range(len(text)))


def test_ing6_mid_line_arrow_is_not_a_bullet() -> None:
    # Was "A → B" unchanged; since the MATH-1 fallback the arrow is spoken by name.
    out, cmap = normalize("A → B")
    assert out == "A goes to B"
    assert set(cmap[2:9]) == {2}


# Roman numerals that label structure are read as numbers (PART II report, 2026-10-17).
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("PART II", "Part two"),
        ("Part II: Wealth", "Part two: Wealth"),
        ("Chapter IV", "Chapter four"),
        ("CHAPTER XIV. The End", "Chapter fourteen. The End"),
        ("Book III", "Book three"),
        ("Act V, Scene ii", "Act five, Scene two"),
        ("Appendix VII", "Appendix seven"),
        ("Volume I", "Volume one"),
        ("Vol. IX of the set", "Vol. nine of the set"),
        ("Section IX applies.", "Section nine applies."),
        ("After World War II ended.", "After World War two ended."),
        ("World War I ended.", "World War one ended."),
        ("Phase XXXIX", "Phase thirty-nine"),
        ("see part iv below", "see part four below"),
        ("Step XXI.", "Step twenty-one."),
    ],
)
def test_ing6_roman_after_structural_word(text: str, expected: str) -> None:
    out, cmap = normalize(text)
    assert out == expected
    assert len(cmap) == len(out)
    assert all(a <= b for a, b in pairwise(cmap))


@pytest.mark.parametrize(
    ("text", "expected"),
    [("II", "two"), ("XIV.", "fourteen."), ("II. Making Money", "two. Making Money")],
)
def test_ing6_roman_heading_alone_or_leading(text: str, expected: str) -> None:
    assert normalize(text, heading=True)[0] == expected
    assert normalize(text)[0] == text  # body text: untouched


@pytest.mark.parametrize(
    ("text", "heading"),
    [
        ("Henry VIII was king.", False),
        ("Mr. X said no.", False),
        ("I", True),
        ("I think so.", True),
        ("It was part I think of the plan.", False),
        ("Louis XIV", True),
        ("Part MMX", False),
        ("Partial II", False),
        ("Part IIa", False),
        ("Part\nII", False),
    ],
)
def test_ing6_roman_negative_cases(text: str, heading: bool) -> None:
    assert normalize(text, heading=heading) == (text, list(range(len(text))))


def test_ing6_roman_char_map_round_trip() -> None:
    text = "PART II: How to Get Rich"
    out, cmap = normalize(text)
    assert out == "Part two: How to Get Rich"
    _assert_expansion_in_span(text, "II", out, cmap, "two")
    assert cmap[:4] == [0, 1, 2, 3]  # "Part" maps to "PART" letter by letter
    tail = out.index(":")
    assert cmap[tail:] == list(range(text.index(":"), len(text)))
    heading = "XXXVIII. Notes"
    out, cmap = normalize(heading, heading=True)
    assert out == "thirty-eight. Notes"
    _assert_expansion_in_span(heading, "XXXVIII", out, cmap, "thirty-eight")
    assert all(0 <= i < len(heading) for i in cmap)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("On a scale of 1–10, I would", "On a scale of 1 to 10, I would"),
        ("See pages 10-12.", "See pages 10 to 12."),
        ("See pp. 10-12.", "See pp. 10 to 12."),
        ("From 1990–1995 it grew.", "From 1990 to 1995 it grew."),
        ("From 1990—1995 it grew.", "From 1990 to 1995 it grew."),
        ("Ages 3 - 5 only.", "Ages 3 to 5 only."),
        ("Ages 3 – 5 only.", "Ages 3 to 5 only."),
        ("A 5–10% gain.", "A 5 to 10 percent gain."),
        ("Walk 5-10km daily.", "Walk 5 to 10km daily."),
        ("(1-3)", "(1 to 3)"),
    ],
)
def test_ing6_numeric_range_read_as_to(text: str, expected: str) -> None:
    out, cmap = normalize(text)
    assert out == expected
    assert len(cmap) == len(out)
    assert all(a <= b for a, b in pairwise(cmap))


@pytest.mark.parametrize(
    "text",
    [
        "ISBN 978-0-12-345678-9 here.",
        "Dated 2026-10-17 today.",
        "Row A-1 is empty.",
        "During COVID-19 we stayed in.",
        "A 3-D film.",
        "Let x-1 be small.",
        "Between 1.5-2 litres.",
        "Ran 9:00-10:00 daily.",
        "Code 12345-6789 here.",
        "Odd 3 -5 spacing.",
    ],
)
def test_ing6_numeric_range_negative_cases(text: str) -> None:
    assert normalize(text) == (text, list(range(len(text))))


def test_ing6_numeric_range_char_map_round_trip() -> None:
    text = "On a scale of 1–10, I would"
    out, cmap = normalize(text)
    assert out == "On a scale of 1 to 10, I would"
    dash = text.index("–")
    o = out.index(" to ")
    assert cmap[o : o + 4] == [dash] * 4  # " to " maps onto the dash
    assert cmap[:o] == list(range(dash))
    assert cmap[o + 4 :] == list(range(dash + 1, len(text)))
    spaced = "Ages 3 - 5 only."
    out, cmap = normalize(spaced)
    o = out.index(" to ")
    assert all(spaced.index(" - ") <= i < spaced.index(" - ") + 3 for i in cmap[o : o + 4])
    assert cmap[o + 4 :] == list(range(spaced.index("5"), len(spaced)))


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "Happiness = Health + Wealth + Good Relationships",
            "Happiness equals Health + Wealth + Good Relationships",
        ),
        ("x = 5", "x equals 5"),
        ("x=5", "x equals 5"),
        ("y=2.5 here", "y equals 2.5 here"),
        ("Very few people disagree 2+2=4, right?", "Very few people disagree 2+2 equals 4, right?"),
        ("a  =  b", "a equals b"),
        ("Sleep = No alarms + 8–9 hours", "Sleep equals No alarms + 8 to 9 hours"),
        (
            "Return on Investment = “Buy-and-Hold” + Valuation",
            "Return on Investment equals “Buy-and-Hold” + Valuation",
        ),
        ("a ≠ b", "a does not equal b"),
        ("x≠5.", "x does not equal 5."),
    ],
)
def test_ing6_equals_sign_read_as_equals(text: str, expected: str) -> None:
    out, cmap = normalize(text)
    assert out == expected
    assert len(cmap) == len(out)
    assert all(a <= b for a, b in pairwise(cmap))


@pytest.mark.parametrize(
    "text",
    [
        "if a == b then",
        "x => y",
        "a <= b",
        "a >= b",
        "a != b",
        "= starts the line",
        "the line ends with =",
        "first line\n= second line",
        "first line =\nsecond line",
        "=== Header ===",
        "x =5 and x= 5",
        "v=2htl-O1oDcI.",
        "utm_ campaign=platform-newsletter&utm_medium=email.",
        "key=value",
        "x=5x",
    ],
)
def test_ing6_equals_sign_negative_cases(text: str) -> None:
    assert normalize(text) == (text, list(range(len(text))))


def test_ing6_equals_sign_char_map_round_trip() -> None:
    text = "Health = Exercise + Diet"
    out, cmap = normalize(text)
    assert out == "Health equals Exercise + Diet"
    o = out.index(" equals ")
    span = range(text.index(" = "), text.index(" = ") + 3)
    assert all(i in span for i in cmap[o : o + 8])  # " equals " maps onto " = "
    assert cmap[:o] == list(range(o))
    assert cmap[o + 8 :] == list(range(text.index("Exercise"), len(text)))
    tight = "so 2+2=4, right"
    out, cmap = normalize(tight)
    o = out.index(" equals ")
    assert cmap[o : o + 8] == [tight.index("=")] * 8
    assert cmap[:o] == list(range(o))
    assert cmap[o + 8 :] == list(range(tight.index("=") + 1, len(tight)))


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "On a scale of 1–10, I would have said 2/10 or 3/10.",
            "On a scale of 1 to 10, I would have said 2 out of 10 or 3 out of 10.",
        ),
        ("9/10 or 10/10", "9 out of 10 or 10 out of 10"),
        ("I give it 95/100!", "I give it 95 out of 100!"),
        ("a 0/10 effort", "a 0 out of 10 effort"),
        ("100/100, perfect", "100 out of 100, perfect"),
        ("(4/10)", "(4 out of 10)"),
    ],
)
def test_ing6_rating_read_as_out_of(text: str, expected: str) -> None:
    out, cmap = normalize(text)
    assert out == expected
    assert len(cmap) == len(out)
    assert all(a <= b for a, b in pairwise(cmap))


@pytest.mark.parametrize(
    "text",
    [
        "after 9/11 everything",
        "add 1/2 cup",
        "3/4 of them",
        "on 10/12/2020 we",
        "open 24/7.",
        "digital/Kindle/eBook",
        "60 km/h",
        "a 2/1000 chance",
        "05/10 padded",
        "101/100 is too much",
        "x2/10 id",
        "/2/10/ path",
        "2/10/2016",
        "2/105",
        "2 / 10 spaced",
        "3/10ths",
    ],
)
def test_ing6_rating_negative_cases(text: str) -> None:
    assert normalize(text) == (text, list(range(len(text))))


def test_ing6_rating_char_map_round_trip() -> None:
    text = "said 2/10 or"
    out, cmap = normalize(text)
    assert out == "said 2 out of 10 or"
    slash = text.index("/")
    o = out.index(" out of ")
    assert cmap[o : o + 8] == [slash] * 8  # " out of " maps onto the slash
    assert cmap[:o] == list(range(slash))
    assert cmap[o + 8 :] == list(range(slash + 1, len(text)))


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "Wealth = Income + Wealth * (Return on Investment)",
            "Wealth equals Income + Wealth times (Return on Investment)",
        ),
        ("3 * 4", "3 times 4"),
        ("a  *  b", "a times b"),
    ],
)
def test_ing6_asterisk_between_terms_read_as_times(text: str, expected: str) -> None:
    out, cmap = normalize(text)
    assert out == expected
    assert len(cmap) == len(out)
    assert all(a <= b for a, b in pairwise(cmap))


@pytest.mark.parametrize(
    "text",
    [
        "a ** b",
        "**bold** text",
        "a footnote* here",
        "see *note",
        "3*4",
        "a *b",
        "a* b",
        "first line\n* second line",
        "the line ends with *",
        "first line *\nsecond line",
    ],
)
def test_ing6_asterisk_negative_cases(text: str) -> None:
    assert normalize(text) == (text, list(range(len(text))))


def test_ing6_asterisk_leading_bullet_stays_silent() -> None:
    assert normalize("* starts the line")[0] == "starts the line"


def test_ing6_asterisk_char_map_round_trip() -> None:
    text = "Wealth * (Return"
    out, cmap = normalize(text)
    assert out == "Wealth times (Return"
    o = out.index(" times ")
    span = range(text.index(" * "), text.index(" * ") + 3)
    assert all(i in span for i in cmap[o : o + 7])  # " times " maps onto " * "
    assert cmap[:o] == list(range(o))
    assert cmap[o + 7 :] == list(range(text.index("("), len(text)))


# Phone numbers (ING-6, user verdict 2026-10-17 on sampler sentence 8): digit groups, never a range.
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Call 555-0123 now.", "Call 5 5 5, 0 1 2 3 now."),
        ("Call 1-800-555-0123.", "Call 1, 8 0 0, 5 5 5, 0 1 2 3."),
        ("Call (415) 555-0123 today.", "Call 4 1 5, 5 5 5, 0 1 2 3 today."),
        ("Ring +44 20 7946 0958.", "Ring plus 4 4, 2 0, 7 9 4 6, 0 9 5 8."),
        ("Call 555-1234-5678 now.", "Call 5 5 5, 1 2 3 4, 5 6 7 8 now."),
        ("Fax 555.123.4567 here.", "Fax 5 5 5, 1 2 3, 4 5 6 7 here."),
        ("Ring +1-800-555-0123.", "Ring plus 1, 8 0 0, 5 5 5, 0 1 2 3."),
    ],
)
def test_ing6_phone_number_read_as_digit_groups(text: str, expected: str) -> None:
    out, cmap = normalize(text)
    assert out == expected
    assert len(cmap) == len(out)
    assert all(a <= b for a, b in pairwise(cmap))


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("See pages 10-12.", "See pages 10 to 12."),
        ("From 2019-2021 it grew.", "From 2019 to 2021 it grew."),
        ("Dated 17-10-2026 today.", "Dated 17-10-2026 today."),
        ("Dated 2026-10-17 today.", "Dated 2026-10-17 today."),
        ("Code 12345-6789 here.", "Code 12345-6789 here."),
        ("IP 192.168.1.100 here.", "IP 192.168.1.100 here."),
        ("ISBN 978-0-12-345678-9 here.", "ISBN 978-0-12-345678-9 here."),
        ("Pi is 3.1415926 roughly.", "Pi is 3.1415926 roughly."),
    ],
)
def test_ing6_phone_number_negative_cases(text: str, expected: str) -> None:
    assert normalize(text)[0] == expected


def test_ing6_phone_number_char_map_round_trip() -> None:
    text = "Call 555-0123 now."
    out, cmap = normalize(text)
    assert out == "Call 5 5 5, 0 1 2 3 now."
    start, end = text.index("555"), text.index(" now")
    o, o_end = out.index("5"), out.index(" now")
    assert cmap[:o] == list(range(start))
    assert cmap[o_end:] == list(range(end, len(text)))
    for k in range(o, o_end):
        assert start <= cmap[k] < end
        if out[k].isdigit():
            assert text[cmap[k]] == out[k]  # every digit points at itself
    dash = text.index("-")
    sep = out.index(", ")
    assert cmap[sep : sep + 2] == [dash, dash]
    intl = "Ring +44 20 7946 0958."
    out, cmap = normalize(intl)
    assert cmap[out.index("plus") : out.index("plus") + 5] == [intl.index("+")] * 5
    assert all(a <= b for a, b in pairwise(cmap))


# Clock hours (ING-6, user verdict 2026-10-17): spoken with a.m. / p.m.
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Open at 9am.", "Open at 9 a.m."),
        ("Open at 9 am today.", "Open at 9 a.m. today."),
        ("Open at 9 a.m. today.", "Open at 9 a.m. today."),
        ("Open at 9AM sharp.", "Open at 9 a.m. sharp."),
        ("Back at 9:30pm we eat.", "Back at 9 30 p.m. we eat."),
        ("Back at 10:05 AM we eat.", "Back at 10 oh 5 a.m. we eat."),
        ("Done by 12:00 PM.", "Done by 12 p.m."),
        ("Leave at 7 P.M., then.", "Leave at 7 p.m., then."),
        ("Call between 9 and 5pm.", "Call between 9 and 5 p.m."),
        ("Call 9-5pm daily.", "Call 9 to 5 p.m. daily."),
    ],
)
def test_ing6_clock_hours_explicit_meridiem(text: str, expected: str) -> None:
    out, cmap = normalize(text)
    assert out == expected
    assert len(cmap) == len(out)
    assert all(a <= b for a, b in pairwise(cmap))


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Call 555-0123 between 9 and 5.", "Call 5 5 5, 0 1 2 3 between 9 a.m. and 5 p.m."),
        (
            "Our office is open from 8 to 4; call 1-800-555-0123 or +44 20 7946 0958.",
            (
                "Our office is open from 8 a.m. to 4 p.m.; call 1, 8 0 0, 5 5 5, 0 1 2 3 or "
                "plus 4 4, 2 0, 7 9 4 6, 0 9 5 8."
            ),
        ),
        (
            "Office hours: from 9 to 5 every weekday.",
            "Office hours: from 9 a.m. to 5 p.m. every weekday.",
        ),
        (
            "We are available between 10 and 6, Monday.",
            "We are available between 10 a.m. and 6 p.m., Monday.",
        ),
    ],
)
def test_ing6_clock_hours_inferred_pair_with_cue(text: str, expected: str) -> None:
    out, cmap = normalize(text)
    assert out == expected
    assert len(cmap) == len(out)
    assert all(a <= b for a, b in pairwise(cmap))


@pytest.mark.parametrize(
    "text",
    [
        "I am 9 years old.",
        "In 2019 am I wrong?",
        "He was 5 amazing times.",
        "Rates rose between 3 and 5 percent.",
        "It rose between 9 and 5.",
        "Call between 3 and 5.",
        "Call between 9 and 10.",
        "The office has between 9 and 5 staff.",
        "Call from 9 and 5.",
        "Ran 9:00-10:00 daily.",
    ],
)
def test_ing6_clock_hours_negative_cases(text: str) -> None:
    assert normalize(text) == (text, list(range(len(text))))


def test_ing6_clock_hours_char_map_round_trip() -> None:
    text = "Open at 9am today."
    out, cmap = normalize(text)
    assert out == "Open at 9 a.m. today."
    nine, am = text.index("9"), text.index("am")
    o = out.index(" a.m.")
    assert cmap[:o] == list(range(nine + 1))
    assert all(am <= i < am + 2 for i in cmap[o : o + 5])
    assert cmap[o + 5 :] == list(range(am + 2, len(text)))
    pair = "Call between 9 and 5."
    out, cmap = normalize(pair)
    o = out.index(" a.m.")
    assert cmap[o : o + 5] == [pair.index("9")] * 5  # inferred: maps onto the hour
    o = out.index(" p.m")
    assert cmap[o : o + 4] == [pair.index("5")] * 4
    assert cmap[-1] == len(pair) - 1  # the sentence period completes "p.m."


# Degrees (ING-6, user verdict on sampler sentence 11, 2026-10-17): never a bare letter.
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "Temperatures reached 40°C, a 15% rise.",
            "Temperatures reached 40 degrees Celsius, a 15 percent rise.",
        ),
        ("It was 40 °C outside.", "It was 40 degrees Celsius outside."),
        ("It was 40° C outside.", "It was 40 degrees Celsius outside."),
        ("Bake at 350°F for an hour.", "Bake at 350 degrees Fahrenheit for an hour."),
        ("Make a 90° turn.", "Make a 90 degrees turn."),
        ("It fell to -5°.", "It fell to -5 degrees."),
        ("It fell to -5°F overnight.", "It fell to -5 degrees Fahrenheit overnight."),
        ("Only 1°C warmer.", "Only 1 degree Celsius warmer."),
        ("Only 1° off.", "Only 1 degree off."),
        ("A 0.5°C rise.", "A 0.5 degrees Celsius rise."),
        ("From 10°C to 20°C.", "From 10 degrees Celsius to 20 degrees Celsius."),
    ],
)
def test_ing6_degrees_spoken(text: str, expected: str) -> None:
    out, cmap = normalize(text)
    assert out == expected
    assert len(cmap) == len(out)
    assert all(a <= b for a, b in pairwise(cmap))


@pytest.mark.parametrize(
    "text",
    [
        "It was 40C outside.",
        "It was 40 C outside.",
        "The ° sign alone.",
        "Units in °C are metric.",
        "Version v2° is odd.",
    ],
)
def test_ing6_degrees_negative_cases(text: str) -> None:
    assert normalize(text) == (text, list(range(len(text))))


def test_ing6_degrees_char_map_round_trip() -> None:
    text = "Temperatures reached 40°C, a 15% rise."
    out, cmap = normalize(text)
    four, deg = text.index("40"), text.index("°")
    o = out.index(" degrees Celsius")
    assert cmap[:o] == list(range(four + 2))
    assert all(deg <= i < deg + 2 for i in cmap[o : o + len(" degrees Celsius")])
    assert cmap[o + len(" degrees Celsius")] == deg + 2  # the comma
    spaced = "It was 40 °C outside."
    out, cmap = normalize(spaced)
    o = out.index(" degrees")
    sp = spaced.index(" °")
    assert all(sp <= i < sp + 3 for i in cmap[o : o + len(" degrees Celsius")])
    assert cmap[-1] == len(spaced) - 1


def test_ing6_interval_after_operator_kept() -> None:
    out = normalize("compactly supported in Kν × [0, 2], and")[0]
    assert "[0, 2]" in out


def test_ing6_numeric_citations_still_dropped() -> None:
    out = normalize("as shown in [1, 2] and [3–5] and [12]")[0]
    assert out == "as shown in and and"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # The brackets are kept; symbols inside are read by the MATH-1 fallback.
        ("on R3 × [0, 1) and [0, ∞) and (0, 1]", "on R3 times [0, 1) and [0, infinity) and (0, 1]"),
        ("the set [0, 2] here", "the set [0, 2] here"),
        ("u ∈ [2, 3] here", "u in [2, 3] here"),
        ("on [a, b] here", "on [a, b] here"),
        ("on [−π, π] here", "on [−pi, pi] here"),
    ],
)
def test_ing6_intervals_kept_as_written(text: str, expected: str) -> None:
    assert normalize(text)[0] == expected


def test_ing6_interval_after_equals_kept() -> None:
    assert normalize("x = [1, 2] here")[0] == "x equals [1, 2] here"


def test_ing6_citation_list_of_three_dropped() -> None:
    assert normalize("prior work [1,2,7] disagrees")[0] == "prior work disagrees"
