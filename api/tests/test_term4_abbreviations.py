"""TERM-4: academic abbreviations spoken by expansion from one table (spec §4c)."""

from itertools import pairwise

import pytest

from hearnarro.ingestion.normalize import normalize

SPEC = {
    "i.e.": "that is",
    "e.g.": "for example",
    "cf.": "compare",
    "w.r.t.": "with respect to",
    "resp.": "respectively",
    "s.t.": "such that",
    "iff": "if and only if",
    "w.l.o.g.": "without loss of generality",
    "viz.": "namely",
    "et seq.": "and following",
    "ibid.": "in the same place",
    "op. cit.": "in the work cited",
}


def test_term4_table_matches_spec() -> None:
    from hearnarro.ingestion.expansions import EXPANSIONS

    assert EXPANSIONS == SPEC


def _invariants(text: str, out: str, cmap: list[int]) -> None:
    assert len(cmap) == len(out)
    assert all(0 <= i < len(text) for i in cmap)
    assert all(a <= b for a, b in pairwise(cmap))


@pytest.mark.parametrize(("token", "expansion"), sorted(SPEC.items()))
def test_term4_expansion_char_map_round_trip(token: str, expansion: str) -> None:
    text = f"the word {token} then more"
    out, cmap = normalize(text)
    assert out == f"the word {expansion} then more"
    _invariants(text, out, cmap)
    start = text.index(token)
    end = start + len(token)
    o = out.index(expansion)
    mapped = cmap[o : o + len(expansion)]
    assert all(start <= i < end for i in mapped), mapped
    assert mapped[0] == start
    assert mapped[-1] == end - 1
    assert cmap[:o] == list(range(o))
    tail = "then more"
    assert [text[i] for i in cmap[-len(tail) :]] == list(tail)


@pytest.mark.parametrize(("token", "expansion"), sorted(SPEC.items()))
def test_term4_case_insensitive(token: str, expansion: str) -> None:
    text = f"so {token.upper()} it"
    out, _ = normalize(text)
    assert out == f"so {expansion} it"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("The rate is fixed, i.e. constant.", "The rate is fixed, that is constant."),
        ("Use a prior, e.g. a Gaussian.", "Use a prior, for example a Gaussian."),
        ("The values are 2 and 3, resp.", "The values are 2 and 3, respectively."),
        (
            "The same source, ibid., gives the date.",
            "The same source, in the same place, gives the date.",
        ),
        ("E.g. trees work.", "For example trees work."),
        ("Find x s.t. the sum is zero.", "Find x such that the sum is zero."),
    ],
)
def test_term4_sentences(text: str, expected: str) -> None:
    out, cmap = normalize(text)
    assert out == expected
    _invariants(text, out, cmap)


@pytest.mark.parametrize(
    "text",
    [
        "The cliff is high.",
        "A sniff test.",
        "Use theorem.g. no",
        "Visit e.gov today",
        "Diffs ie and eg",
    ],
)
def test_term4_only_whole_tokens(text: str) -> None:
    out, _ = normalize(text)
    for expansion in SPEC.values():
        assert expansion not in out


def test_term4_sentence_split_unchanged() -> None:
    from hearnarro.ingestion import abbreviations

    assert not hasattr(abbreviations, "EXPANSIONS")
