"""TERM-2: pronunciation overrides. Migration 0006, the repo functions, the three routes,
global-under-document precedence, cache invalidation by whole token (rows and files, the
``invalidated`` count), and ``SynthContext.lexicon`` reaching a recording backend."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

from tests.test_api_documents import client_for
from yomikoe.storage import repo
from yomikoe.storage.db import (
    MIGRATIONS_DIR,
    connect_sync,
    db_path,
    engine,
    pack_char_map,
    run_migrations,
    sync_url,
)
from yomikoe.synthesis.backend import SynthContext, SynthResult
from yomikoe.synthesis.encode import WavEncoder
from yomikoe.synthesis.fake import FakeBackend

# segment id -> (document id, normalized text)
SEGMENTS = {
    100: (1, "The Navier equations hold."),
    101: (1, "Nothing here, navierish is not a token."),
    102: (1, "NAVIER again, upper case."),
    200: (2, "Navier in the second document."),
    201: (2, "Plain prose only."),
}


def _cfg(data_dir: Path) -> Config:
    cfg = Config()
    cfg.set_main_option("script_location", str(MIGRATIONS_DIR))
    cfg.set_main_option("sqlalchemy.url", sync_url(db_path(data_dir)).replace("%", "%%"))
    return cfg


def _seed(data_dir: Path, *, with_cache: bool = True) -> None:
    run_migrations(data_dir)
    with connect_sync(db_path(data_dir)) as conn:
        for doc in (1, 2):
            conn.execute(
                "INSERT INTO documents (id, title, filename, sha256, status, created_at) "
                "VALUES (?, 't', 'f.pdf', ?, 'ready', '2026-10-20')",
                (doc, f"sha{doc}"),
            )
            conn.execute(
                'INSERT INTO blocks (id, document_id, page, "order", type, merged_text) '
                "VALUES (?, ?, 1, 0, 'body', 'x')",
                (doc * 10, doc),
            )
        for order, (sid, (doc, text)) in enumerate(SEGMENTS.items()):
            conn.execute(
                'INSERT INTO segments (id, document_id, block_id, "order", text, normalized_text, '
                "char_start, char_end, char_map) VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?)",
                (
                    sid,
                    doc,
                    doc * 10,
                    order,
                    text,
                    text,
                    len(text),
                    pack_char_map(list(range(len(text)))),
                ),
            )
            if with_cache:
                rel = f"audio/{doc}/{sid}.wav"
                (data_dir / rel).parent.mkdir(parents=True, exist_ok=True)
                (data_dir / rel).write_bytes(b"RIFF")
                conn.execute(
                    "INSERT INTO audio_cache (segment_id, voice_id, speed, backend, status, path, "
                    "created_at) VALUES (?, 'fake_f1', 1.0, 'fake', 'ready', ?, 'x')",
                    (sid, rel),
                )


def _cached(data_dir: Path) -> set[int]:
    with connect_sync(db_path(data_dir)) as conn:
        rows = {r[0] for r in conn.execute("SELECT segment_id FROM audio_cache")}
    files = {int(p.stem) for p in (data_dir / "audio").rglob("*.wav")}
    assert rows == files, (rows, files)
    return rows


# claim 1 -------------------------------------------------------------------------------------


def test_term2_migration_0006_upgrade_and_downgrade(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    command.upgrade(cfg, "0005")
    with connect_sync(db_path(tmp_path)) as conn:
        conn.execute(
            "INSERT INTO documents (id, title, filename, sha256, status, created_at) "
            "VALUES (1, 'm5', 'f.pdf', 'sha1', 'ready', '2026-10-20')"
        )
        assert not conn.execute(
            "SELECT 1 FROM sqlite_master WHERE name = 'pronunciations'"
        ).fetchone()
    command.upgrade(cfg, "0006")
    with connect_sync(db_path(tmp_path)) as conn:
        cols = {r[1]: r for r in conn.execute("PRAGMA table_info(pronunciations)")}
        assert set(cols) == {"id", "document_id", "word", "respelling", "created_at"}
        assert cols["word"][3] == 1 and cols["respelling"][3] == 1  # NOT NULL
        assert cols["document_id"][3] == 0
        fks = list(conn.execute("PRAGMA foreign_key_list(pronunciations)"))
        assert fks and fks[0][2] == "documents" and fks[0][6] == "CASCADE"
        conn.execute(
            "INSERT INTO pronunciations (document_id, word, respelling) VALUES (1, 'navier', 'nav')"
        )
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO pronunciations (document_id, word, respelling) "
                "VALUES (1, 'navier', 'x')"
            )
        conn.execute(
            "INSERT INTO pronunciations (document_id, word, respelling) VALUES (NULL, 'eta', 'ay')"
        )
        with pytest.raises(sqlite3.IntegrityError):  # one global row per word too
            conn.execute(
                "INSERT INTO pronunciations (document_id, word, respelling) "
                "VALUES (NULL, 'eta', 'ee')"
            )
        conn.execute("DELETE FROM documents WHERE id = 1")
        assert conn.execute("SELECT count(*) FROM pronunciations").fetchone()[0] == 1  # cascade
    command.downgrade(cfg, "0005")
    with connect_sync(db_path(tmp_path)) as conn:
        assert not conn.execute(
            "SELECT 1 FROM sqlite_master WHERE name = 'pronunciations'"
        ).fetchone()
    command.upgrade(cfg, "head")


# claim 2 -------------------------------------------------------------------------------------


async def test_term2_repo_upsert_lowercase_and_merge(tmp_path: Path) -> None:
    _seed(tmp_path, with_cache=False)
    async with engine(tmp_path).connect() as conn:
        g = await repo.put_pronunciation(conn, None, "Navier", "nav-YAY")
        g2 = await repo.put_pronunciation(conn, None, "NAVIER", "nahv-YAY")
        assert g2["id"] == g["id"] and g2["word"] == "navier" and g2["respelling"] == "nahv-YAY"
        await repo.put_pronunciation(conn, None, "Euler", "OY-ler")
        d = await repo.put_pronunciation(conn, 1, "Navier", "NAV-ee-ay")
        d2 = await repo.put_pronunciation(conn, 1, "navier", "nav-ee-AY")
        assert d2["id"] == d["id"] and d2["document_id"] == 1
        assert [r["word"] for r in await repo.list_pronunciations(conn, None)] == [
            "euler",
            "navier",
        ]
        assert len(await repo.list_pronunciations(conn, 1)) == 1
        assert await repo.pronunciations_for(conn, 1) == {"navier": "nav-ee-AY", "euler": "OY-ler"}
        assert await repo.pronunciations_for(conn, 2) == {"navier": "nahv-YAY", "euler": "OY-ler"}
        assert await repo.delete_pronunciation(conn, d["id"]) is not None
        assert await repo.delete_pronunciation(conn, d["id"]) is None
        assert (await repo.pronunciations_for(conn, 1))["navier"] == "nahv-YAY"


# claim 3 -------------------------------------------------------------------------------------


async def test_term2_routes_shapes_422_404(tmp_path: Path) -> None:
    _seed(tmp_path, with_cache=False)
    async with client_for(tmp_path) as client:
        r = await client.put(
            "/pronunciations", json={"document_id": 1, "word": "Navier", "respelling": "nav-YAY"}
        )
        assert r.status_code == 200, r.text
        row = r.json()
        assert set(row) == {"id", "document_id", "word", "respelling", "created_at", "invalidated"}
        assert row["word"] == "navier" and row["document_id"] == 1 and row["invalidated"] == 0
        g = await client.put(
            "/pronunciations", json={"document_id": None, "word": "eta", "respelling": "AY-ta"}
        )
        assert g.status_code == 200 and g.json()["document_id"] is None
        listed = (await client.get("/pronunciations", params={"document_id": 1})).json()
        assert [x["word"] for x in listed] == ["navier"]
        assert set(listed[0]) == {"id", "document_id", "word", "respelling", "created_at"}
        assert [x["word"] for x in (await client.get("/pronunciations")).json()] == ["eta"]
        for bad in ({"word": "  ", "respelling": "x"}, {"word": "eta", "respelling": "12 -"}):
            bad_r = await client.put("/pronunciations", json={"document_id": 1, **bad})
            assert bad_r.status_code == 422, bad
        assert (await client.get("/pronunciations", params={"document_id": 99})).status_code == 404
        missing = await client.put(
            "/pronunciations", json={"document_id": 99, "word": "a", "respelling": "b"}
        )
        assert missing.status_code == 404
        d = await client.delete(f"/pronunciations/{row['id']}")
        assert d.status_code == 200 and d.json() == {"invalidated": 0}
        assert (await client.delete(f"/pronunciations/{row['id']}")).status_code == 404
        paths = set(client.app.openapi()["paths"])  # type: ignore[attr-defined]
        assert {"/pronunciations", "/pronunciations/{pronunciation_id}"} <= paths


# claim 4 -------------------------------------------------------------------------------------


async def test_term2_change_purges_segments_with_the_word(tmp_path: Path) -> None:
    _seed(tmp_path)
    assert _cached(tmp_path) == set(SEGMENTS)
    async with client_for(tmp_path) as client:
        r = await client.put(
            "/pronunciations", json={"document_id": 1, "word": "navier", "respelling": "nav-YAY"}
        )
        assert r.json()["invalidated"] == 2  # 100 and 102 (case-insensitive); not "navierish"
        assert _cached(tmp_path) == {101, 200, 201}
        g = await client.put(
            "/pronunciations", json={"document_id": None, "word": "Navier", "respelling": "nav"}
        )
        assert g.json()["invalidated"] == 1  # 200 in document 2; 100, 102 already gone
        assert _cached(tmp_path) == {101, 201}
        p = await client.put(
            "/pronunciations", json={"document_id": None, "word": "prose", "respelling": "prohz"}
        )
        assert p.json()["invalidated"] == 1
        assert _cached(tmp_path) == {101}
        d = await client.delete(f"/pronunciations/{p.json()['id']}")
        assert d.json() == {"invalidated": 0}


def test_term2_purge_segments_helper(tmp_path: Path) -> None:
    from yomikoe.cli import purge_segments

    _seed(tmp_path)
    conn = connect_sync(db_path(tmp_path))
    try:
        assert purge_segments(conn, [], tmp_path) == 0
        assert purge_segments(conn, [100, 200], tmp_path) == 2
    finally:
        conn.close()
    assert _cached(tmp_path) == {101, 102, 201}
    assert not (tmp_path / "audio" / "2" / "200.wav").exists()


# claim 5 -------------------------------------------------------------------------------------


class RecordingBackend(FakeBackend):
    def __init__(self) -> None:
        self.contexts: list[SynthContext | None] = []

    def synthesize(
        self, text: str, voice_id: str, speed: float, context: SynthContext | None = None
    ) -> SynthResult:
        self.contexts.append(context)
        return super().synthesize(text, voice_id, speed, context)


async def test_term2_lexicon_reaches_backend_and_context_is_dropped(tmp_path: Path) -> None:
    _seed(tmp_path, with_cache=False)
    backend = RecordingBackend()
    async with client_for(
        tmp_path, tts_backend=backend, encoder=WavEncoder(), lookahead=0
    ) as client:
        audio = {"voice": "fake_f1", "speed": 1.0}
        assert (await client.get("/audio/100", params=audio)).status_code == 200
        assert backend.contexts[-1] is None  # no acronyms, no overrides
        await client.put(
            "/pronunciations", json={"document_id": 1, "word": "Navier", "respelling": "nav-YAY"}
        )
        assert (await client.get("/audio/100", params=audio)).status_code == 200
        ctx = backend.contexts[-1]
        assert ctx is not None and ctx.lexicon == {"navier": "nav-YAY"} and ctx.acronyms == {}
        await client.put(
            "/pronunciations", json={"document_id": None, "word": "the", "respelling": "thuh"}
        )  # global: purges 100 ("The") and drops every cached context
        assert (await client.get("/audio/100", params=audio)).status_code == 200
        assert backend.contexts[-1].lexicon == {"navier": "nav-YAY", "the": "thuh"}
        assert (await client.get("/audio/200", params=audio)).status_code == 200
        assert backend.contexts[-1].lexicon == {"the": "thuh"}
        assert backend.contexts[-1].document_id == 2
