"""SYN-4 (MATH-1..4, M5 listening sheet 2026-10-22): in mathematics the variable "a" is voiced as
the letter (misaki ``A`` = /eɪ/), never as the article (/ə/); "a book" in prose keeps the article.

The synthesis service tells the backend which normalized-text offsets are maths
(``SynthContext.math_spans``): the whole text of an equation segment, or the normalized offsets
whose ``char_map`` source falls inside a ``math_json`` range of a body segment. The Kokoro
backend re-voices a standalone "a"/"A" token inside those spans (``voice_math_letters``).
"""

from __future__ import annotations

import json
import logging
from functools import cache
from pathlib import Path
from typing import Any

import pytest

from tests.test_api_documents import client_for
from yomikoe.storage.db import connect_sync, db_path, pack_char_map, run_migrations
from yomikoe.synthesis.backend import SynthContext, SynthResult
from yomikoe.synthesis.encode import WavEncoder
from yomikoe.synthesis.fake import FakeBackend

ARTICLE = "ɐ"
LETTER_A = "ˈA"  # misaki's letter name: /eɪ/


@cache
def _g2p() -> Any:
    try:
        from yomikoe.synthesis import kokoro_backend

        logging.getLogger(kokoro_backend.__name__).setLevel(logging.ERROR)
        return kokoro_backend.build_g2p(False, kokoro_backend.model_vocab())
    except Exception as e:  # noqa: BLE001 - no misaki/spaCy/config here: skip
        pytest.skip(f"voice front-end unavailable: {type(e).__name__}: {e}")


def _voiced(text: str, spans: list[tuple[int, int]]) -> list[tuple[str, str]]:
    from yomikoe.synthesis.kokoro_backend import voice_math_letters

    _, tokens = _g2p()(text)
    voice_math_letters(text, tokens, spans)
    return [(t.text, t.phonemes) for t in tokens if t.text.strip()]


def test_syn4_letter_a_inline_range_voiced_as_letter() -> None:
    toks = _voiced("where a in b of x", [(6, 17)])
    assert toks[1] == ("a", LETTER_A)
    assert toks[2][0] == "in"


def test_syn4_letter_a_equation_voiced_as_letter() -> None:
    toks = _voiced("a sub t, i distributed as", [(0, 25)])
    assert toks[0] == ("a", LETTER_A)


def test_syn4_letter_a_prose_keeps_article() -> None:
    toks = _voiced("a book about a theorem", [])
    assert [p for w, p in toks if w == "a"] == [ARTICLE, ARTICLE]


def test_syn4_letter_a_only_inside_the_span() -> None:
    text = "A in B, where A is a set"
    toks = _voiced(text, [(0, 6), (14, 15)])
    assert [p for w, p in toks if w.lower() == "a"] == [LETTER_A, LETTER_A, ARTICLE]


def test_syn4_letter_a_no_spans_is_a_no_op() -> None:
    from yomikoe.synthesis.kokoro_backend import voice_math_letters

    _, tokens = _g2p()("where a in b")
    assert voice_math_letters("where a in b", tokens, ()) == 0
    assert tokens[1].phonemes == ARTICLE


# the service: which offsets are maths reaches the backend ------------------------------------

# text "where a∈b(x) holds" -> normalized "where a in b of x holds"; maths range text[6:12]
TEXT = "where a∈b(x) holds"
NORM = "where a in b of x holds"
CMAP = [0, 1, 2, 3, 4, 5, 6, 7, 7, 7, 7, 8, 9, 9, 9, 9, 10, 12, 13, 14, 15, 16, 17]
EQ = "a sub t, i distributed as"
PROSE = "a book about a theorem"


def _seed(data_dir: Path) -> None:
    assert len(CMAP) == len(NORM)
    run_migrations(data_dir)
    with connect_sync(db_path(data_dir)) as conn:
        conn.execute(
            "INSERT INTO documents (id, title, filename, sha256, status, created_at) "
            "VALUES (1, 't', 'f.pdf', 'sha1', 'ready', '2026-10-22')"
        )
        for bid, btype in ((10, "body"), (11, "equation")):
            conn.execute(
                'INSERT INTO blocks (id, document_id, page, "order", type, merged_text) '
                "VALUES (?, 1, 1, ?, ?, 'x')",
                (bid, bid, btype),
            )
        rows = [
            (100, 10, TEXT, NORM, CMAP, json.dumps([{"start": 6, "end": 12, "display": False}])),
            (101, 11, EQ, EQ, list(range(len(EQ))), None),
            (102, 10, PROSE, PROSE, list(range(len(PROSE))), None),
        ]
        for order, (sid, bid, text, norm, cmap, mj) in enumerate(rows):
            conn.execute(
                'INSERT INTO segments (id, document_id, block_id, "order", text, normalized_text, '
                "char_start, char_end, char_map, math_json) VALUES (?, 1, ?, ?, ?, ?, 0, ?, ?, ?)",
                (sid, bid, order, text, norm, len(text), pack_char_map(cmap), mj),
            )


class RecordingBackend(FakeBackend):
    def __init__(self) -> None:
        self.contexts: list[SynthContext | None] = []

    def synthesize(
        self, text: str, voice_id: str, speed: float, context: SynthContext | None = None
    ) -> SynthResult:
        self.contexts.append(context)
        return super().synthesize(text, voice_id, speed, context)


async def test_syn4_letter_a_math_spans_reach_backend(tmp_path: Path) -> None:
    _seed(tmp_path)
    backend = RecordingBackend()
    async with client_for(
        tmp_path, tts_backend=backend, encoder=WavEncoder(), lookahead=0
    ) as client:
        audio = {"voice": "fake_f1", "speed": 1.0}
        assert (await client.get("/audio/100", params=audio)).status_code == 200
        ctx = backend.contexts[-1]
        assert ctx is not None and ctx.math_spans == ((6, 17),) and ctx.document_id == 1
        assert NORM[6:17] == "a in b of x"
        assert (await client.get("/audio/101", params=audio)).status_code == 200
        assert backend.contexts[-1].math_spans == ((0, len(EQ)),)
        assert (await client.get("/audio/102", params=audio)).status_code == 200
        assert backend.contexts[-1] is None  # prose, no acronyms, no overrides
