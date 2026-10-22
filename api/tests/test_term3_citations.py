"""TERM-3: author-year citations spoken or skipped by the document profile (spec §4c)."""

from dataclasses import replace
from itertools import pairwise

import pytest

from yomikoe.ingestion.normalize import normalize
from yomikoe.ingestion.profile import PROSE_DEFAULT, DocumentProfile

READ = replace(PROSE_DEFAULT, author_year_citations="read")
SKIP = replace(PROSE_DEFAULT, author_year_citations="skip")
MATH_SKIP = replace(PROSE_DEFAULT, cls="math", author_year_citations="skip")

READ_CASES = [
    ("This was shown before (Smith et al., 2019).", "This was shown before Smith et al 2019."),
    ("The method is standard (Jones, 2020).", "The method is standard Jones 2020."),
    ("Prior work agrees (Lee and Kim, 2018).", "Prior work agrees Lee and Kim 2018."),
    ("Results vary (Brown & Davis, 2021).", "Results vary Brown and Davis 2021."),
    ("The result was extended (Miller, 2019a).", "The result was extended Miller 2019a."),
    ("Harvard style (Smith 2019) too.", "Harvard style Smith 2019 too."),
    (
        "Both agree (Smith, 2019; Jones et al., 2020) here.",
        "Both agree Smith 2019, Jones et al 2020 here.",
    ),
    ("(Turing, 1950) is old.", "Turing 1950 is old."),
]

SKIP_CASES = [
    ("This was shown before (Smith et al., 2019).", "This was shown before."),
    ("As (Jones, 2020) shows, it holds.", "As shows, it holds."),
    ("Both agree (Smith, 2019; Jones et al., 2020) here.", "Both agree here."),
    ("Prior work agrees (Lee and Kim, 2018), so we", "Prior work agrees, so we"),
]

NUMERIC_CASES = [
    ("This is known [12, 14].", "This is known."),
    ("The bound is tight [3].", "The bound is tight."),
    ("Several papers report it [5–8].", "Several papers report it."),
]

UNCHANGED = [
    "A plain aside (see above) stays.",
    "The interval (0, 1) is open.",
]


def _invariants(text: str, out: str, cmap: list[int]) -> None:
    assert len(cmap) == len(out)
    assert all(0 <= i < len(text) for i in cmap)
    assert all(a <= b for a, b in pairwise(cmap))


@pytest.mark.parametrize(("text", "expected"), READ_CASES)
@pytest.mark.parametrize("profile", [PROSE_DEFAULT, READ], ids=["default", "read"])
def test_term3_author_year_read(text: str, expected: str, profile: DocumentProfile) -> None:
    out, cmap = normalize(text, profile=profile)
    assert out == expected
    _invariants(text, out, cmap)


def test_term3_default_profile_reads() -> None:
    assert PROSE_DEFAULT.author_year_citations == "read"


@pytest.mark.parametrize(("text", "expected"), SKIP_CASES)
def test_term3_author_year_skip(text: str, expected: str) -> None:
    out, cmap = normalize(text, profile=SKIP)
    assert out == expected
    _invariants(text, out, cmap)


@pytest.mark.parametrize(("text", "expected"), NUMERIC_CASES)
@pytest.mark.parametrize("profile", [PROSE_DEFAULT, READ, SKIP], ids=["default", "read", "skip"])
def test_term3_numeric_clusters_still_dropped(
    text: str, expected: str, profile: DocumentProfile
) -> None:
    out, cmap = normalize(text, profile=profile)
    assert out == expected
    _invariants(text, out, cmap)


@pytest.mark.parametrize("text", UNCHANGED)
@pytest.mark.parametrize("profile", [READ, SKIP], ids=["read", "skip"])
def test_term3_non_citations_untouched(text: str, profile: DocumentProfile) -> None:
    out, _ = normalize(text, profile=profile)
    assert out == text


def test_term3_narrative_citation_keeps_year_brackets() -> None:
    # Narrative form is not the §2a parenthetical: only "et al." is spoken "et al" (ING-6).
    for profile in (READ, SKIP):
        assert normalize("Smith et al. (2019) proved it.", profile=profile)[0] == (
            "Smith et al (2019) proved it."
        )


def test_term3_phone_area_code_not_a_citation() -> None:
    text = "Call (415) 555-0123 now."
    assert normalize(text, profile=SKIP) == normalize(text, profile=READ)
    assert "4 1 5" in normalize(text, profile=SKIP)[0]


def test_term3_read_char_map_round_trip() -> None:
    text = "shown (Smith et al., 2019) here"
    out, cmap = normalize(text, profile=READ)
    assert out == "shown Smith et al 2019 here"
    start, end = text.index("("), text.index(")") + 1
    o = out.index("Smith")
    spoken = "Smith et al 2019"
    mapped = cmap[o : o + len(spoken)]
    assert all(start <= i < end for i in mapped), mapped
    # surname and year map onto their own source letters
    assert [text[i] for i in mapped[:5]] == list("Smith")
    assert [text[i] for i in mapped[-4:]] == list("2019")
    assert [text[i] for i in cmap[o + 6 : o + 11]] == list("et al")
    _invariants(text, out, cmap)


def test_term3_skip_char_map_round_trip() -> None:
    text = "as shown (Smith, 2019) here"
    out, cmap = normalize(text, profile=SKIP)
    assert out == "as shown here"
    assert cmap[:8] == list(range(8))
    assert text[cmap[8]] == " "
    assert [text[i] for i in cmap[9:]] == list("here")


def test_term3_inside_maths_span_copied_under_math_profile() -> None:
    text = "f(Smith, 2019) here"
    out, _ = normalize(text, profile=MATH_SKIP, math_spans=[(0, 14)])
    assert out == "f of (Smith, 2019) here"
