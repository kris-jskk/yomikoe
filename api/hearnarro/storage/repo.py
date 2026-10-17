"""Async repository functions over one aiosqlite connection (D7 tables; ING-1)."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from typing import Any

import aiosqlite

DOCUMENT_COLUMNS = (
    "id, title, filename, sha256, page_count, pages_done, parse_ms, status, fail_reason, "
    "voice_id, speed, acronyms_json, "
    "position_segment_id, position_offset_ms, created_at, last_opened_at"
)
DuplicateDocument = sqlite3.IntegrityError


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


async def _one(conn: aiosqlite.Connection, sql: str, params: tuple[Any, ...]) -> dict | None:
    async with conn.execute(sql, params) as cur:
        row = await cur.fetchone()
    return dict(row) if row is not None else None


async def _all(conn: aiosqlite.Connection, sql: str, params: tuple[Any, ...]) -> list[dict]:
    async with conn.execute(sql, params) as cur:
        return [dict(r) for r in await cur.fetchall()]


async def get_document(conn: aiosqlite.Connection, document_id: int) -> dict[str, Any] | None:
    return await _one(
        conn, f"SELECT {DOCUMENT_COLUMNS} FROM documents WHERE id = ?", (document_id,)
    )


def document_acronyms(doc: dict[str, Any]) -> dict[str, str]:
    """``documents.acronyms_json`` as a dict ({} when NULL: ingested before migration 0003)."""
    raw = doc.get("acronyms_json")
    return dict(json.loads(raw)) if raw else {}


async def get_document_acronyms(conn: aiosqlite.Connection, document_id: int) -> dict[str, str]:
    row = await _one(conn, "SELECT acronyms_json FROM documents WHERE id = ?", (document_id,))
    return document_acronyms(row) if row else {}


async def get_document_by_sha256(conn: aiosqlite.Connection, sha256: str) -> dict[str, Any] | None:
    return await _one(conn, f"SELECT {DOCUMENT_COLUMNS} FROM documents WHERE sha256 = ?", (sha256,))


async def list_documents(conn: aiosqlite.Connection) -> list[dict[str, Any]]:
    return await _all(conn, f"SELECT {DOCUMENT_COLUMNS} FROM documents ORDER BY id", ())


async def insert_document(
    conn: aiosqlite.Connection, *, title: str, filename: str, sha256: str, status: str
) -> int:
    """Insert and commit; raises ``DuplicateDocument`` when the sha256 already exists."""
    cur = await conn.execute(
        "INSERT INTO documents (title, filename, sha256, status, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (title, filename, sha256, status, now_iso()),
    )
    await conn.commit()
    assert cur.lastrowid is not None
    return int(cur.lastrowid)


async def set_status(
    conn: aiosqlite.Connection, document_id: int, status: str, fail_reason: str | None = None
) -> None:
    await conn.execute(
        "UPDATE documents SET status = ?, fail_reason = ? WHERE id = ?",
        (status, fail_reason, document_id),
    )
    await conn.commit()


async def list_sections(conn: aiosqlite.Connection, document_id: int) -> list[dict[str, Any]]:
    return await _all(
        conn,
        "SELECT id, title, level, first_segment_id FROM sections WHERE document_id = ? ORDER BY id",
        (document_id,),
    )


async def count_segments(conn: aiosqlite.Connection, document_id: int) -> int:
    row = await _one(
        conn, "SELECT count(*) AS n FROM segments WHERE document_id = ?", (document_id,)
    )
    return int(row["n"]) if row else 0


async def list_segments(
    conn: aiosqlite.Connection, document_id: int, from_order: int, limit: int
) -> list[dict[str, Any]]:
    """Range scan on the unique index segments(document_id, "order"); ``type`` is the block type."""
    return await _all(
        conn,
        'SELECT s.id, s."order", s.block_id, b.type, s.section_id, s.text, s.normalized_text, '
        "s.char_start, s.char_end "
        "FROM segments s JOIN blocks b ON b.id = s.block_id "
        'WHERE s.document_id = ? AND s."order" >= ? ORDER BY s."order" LIMIT ?',
        (document_id, from_order, limit),
    )


SEGMENT_COLUMNS = (
    'id, document_id, block_id, "order", section_id, text, normalized_text, '
    "char_start, char_end, char_map"
)


async def get_segment_row(conn: aiosqlite.Connection, segment_id: int) -> dict[str, Any] | None:
    """One ``segments`` row with its packed ``char_map`` (SYN-1 timestamp translation)."""
    return await _one(conn, f"SELECT {SEGMENT_COLUMNS} FROM segments WHERE id = ?", (segment_id,))


async def segment_rows_from(
    conn: aiosqlite.Connection, document_id: int, from_order: int, limit: int
) -> list[dict[str, Any]]:
    """Rows of one document with ``order >= from_order`` in reading order (SYN-5 lookahead)."""
    return await _all(
        conn,
        f'SELECT {SEGMENT_COLUMNS} FROM segments WHERE document_id = ? AND "order" >= ? '
        'ORDER BY "order" LIMIT ?',
        (document_id, from_order, limit),
    )
