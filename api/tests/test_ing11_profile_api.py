"""ING-11, LIB-1: the summary ``profile`` fields, the PATCH class override that re-normalizes
through ``renormalize_document`` and drops cache rows, 422, 409, and migration 0005 on an M4
database."""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config

from hearnarro.ingestion.profile import PROSE_DEFAULT
from hearnarro.storage.db import (
    MIGRATIONS_DIR,
    connect_sync,
    db_path,
    pack_char_map,
    run_migrations,
    sync_url,
)
from tests.test_api_documents import client_for

TEXT = "We read Chapter IV twice."
STALE = "We read Chapter IV twice."  # renormalize rewrites it ("Chapter four")


def _seed(data_dir: Path, profile_json: str | None) -> None:
    run_migrations(data_dir)
    with connect_sync(db_path(data_dir)) as conn:
        conn.execute(
            "INSERT INTO documents (id, title, filename, sha256, status, created_at, "
            "profile_json) VALUES (1, 't', 'f.pdf', 'sha1', 'ready', '2026-10-17', ?)",
            (profile_json,),
        )
        conn.execute(
            'INSERT INTO blocks (id, document_id, page, "order", type, merged_text) '
            "VALUES (10, 1, 1, 0, 'body', ?)",
            (TEXT,),
        )
        conn.execute(
            'INSERT INTO segments (id, document_id, block_id, "order", text, normalized_text, '
            "char_start, char_end, char_map) VALUES (100, 1, 10, 0, ?, ?, 0, ?, ?)",
            (TEXT, STALE, len(TEXT), pack_char_map(list(range(len(STALE))))),
        )
        conn.execute(
            "INSERT INTO audio_cache (segment_id, voice_id, speed, backend, status, path, "
            "created_at) VALUES (100, 'af_heart', 1.0, 'kokoro', 'ready', 'audio/1/x.webm', 'x')"
        )


def _cache_rows(data_dir: Path) -> int:
    with connect_sync(db_path(data_dir)) as conn:
        return conn.execute("SELECT count(*) FROM audio_cache").fetchone()[0]


async def test_ing11_summary_carries_profile(tmp_path: Path) -> None:
    computed = PROSE_DEFAULT.with_override(None)
    _seed(tmp_path, computed.to_json())
    async with client_for(tmp_path) as client:
        listed = (await client.get("/documents")).json()[0]["profile"]
        one = (await client.get("/documents/1")).json()["profile"]
    assert listed == one
    assert one["class"] == "prose" and one["computed_class"] == "prose"
    assert one["override"] is None
    for key in ("math_share", "code_share", "citation_style", "scanned_share"):
        assert key in one
    assert one["author_year_citations"] == "read"


async def test_ing11_patch_class_override_renormalizes_and_drops_cache(tmp_path: Path) -> None:
    _seed(tmp_path, PROSE_DEFAULT.to_json())
    async with client_for(tmp_path) as client:
        r = await client.patch("/documents/1", json={"profile": {"class": "math"}})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["profile"]["class"] == "math"
        assert body["profile"]["override"] == "math"
        assert body["profile"]["computed_class"] == "prose"
        assert body["renormalized"] == {"changed": 1, "removed": 1}
        assert _cache_rows(tmp_path) == 0
        with connect_sync(db_path(tmp_path)) as conn:
            norm = conn.execute("SELECT normalized_text FROM segments").fetchone()[0]
        assert norm == "We read Chapter four twice."
        again = (await client.patch("/documents/1", json={"profile": {"class": "math"}})).json()
        assert again["renormalized"] == {"changed": 0, "removed": 0}
        cleared = (await client.patch("/documents/1", json={"profile": {"class": None}})).json()
        assert cleared["profile"]["class"] == "prose" and cleared["profile"]["override"] is None


async def test_ing11_patch_unknown_class_is_422(tmp_path: Path) -> None:
    _seed(tmp_path, None)
    async with client_for(tmp_path) as client:
        r = await client.patch("/documents/1", json={"profile": {"class": "algebra"}})
    assert r.status_code == 422


async def test_ing11_patch_profile_while_parsing_is_409(tmp_path: Path) -> None:
    _seed(tmp_path, None)
    async with client_for(tmp_path) as client:
        with connect_sync(db_path(tmp_path)) as conn:
            conn.execute("UPDATE documents SET status = 'parsing' WHERE id = 1")
        r = await client.patch("/documents/1", json={"profile": {"class": "math"}})
    assert r.status_code == 409


async def test_ing11_migration_0005_on_m4_database(tmp_path: Path) -> None:
    tmp_path.mkdir(exist_ok=True)
    cfg = Config()
    cfg.set_main_option("script_location", str(MIGRATIONS_DIR))
    cfg.set_main_option("sqlalchemy.url", sync_url(db_path(tmp_path)).replace("%", "%%"))
    command.upgrade(cfg, "0004")  # an M4 data dir
    with connect_sync(db_path(tmp_path)) as conn:
        conn.execute(
            "INSERT INTO documents (id, title, filename, sha256, status, created_at) "
            "VALUES (1, 'm4', 'f.pdf', 'sha1', 'ready', '2026-10-17')"
        )
    run_migrations(tmp_path)  # upgrade head
    with connect_sync(db_path(tmp_path)) as conn:
        doc_cols = {r[1] for r in conn.execute("PRAGMA table_info(documents)")}
        seg_cols = {r[1] for r in conn.execute("PRAGMA table_info(segments)")}
        assert conn.execute("SELECT profile_json FROM documents").fetchone()[0] is None
    assert "profile_json" in doc_cols and "math_json" in seg_cols
    async with client_for(tmp_path) as client:
        profile = (await client.get("/documents/1")).json()["profile"]
    assert profile["class"] == "prose" and profile["override"] is None
