"""Stage 5 normalization for speech with char_map (subset of ING-6)."""

from itertools import pairwise

import pytest

from hearnarro.ingestion.normalize import SPOKEN_ACRONYMS, normalize

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
    assert out == "see arxiv.org now"
    url = "https://arxiv.org/abs/1"
    start = text.index(url)
    o = out.index("arxiv.org")
    assert all(start <= i < start + len(url) for i in cmap[o : o + len("arxiv.org")])


def test_ing6_www_url_keeps_host_only() -> None:
    out, _ = normalize("Visit www.example.com/page today.")
    assert "example.com" in out
    assert "/page" not in out


def test_ing6_all_caps_spelled_out() -> None:
    text = "open the PDF file"
    out, cmap = normalize(text)
    assert out == "open the P D F file"
    _assert_expansion_in_span(text, "PDF", out, cmap, "P D F")


def test_ing6_spoken_acronym_unchanged() -> None:
    assert "NASA" in SPOKEN_ACRONYMS
    text = "ask NASA today"
    assert normalize(text) == (text, list(range(len(text))))
