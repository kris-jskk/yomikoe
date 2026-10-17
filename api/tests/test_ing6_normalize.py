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
        "Use e.g. a cat.",
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
