"""Pronunciation override endpoints (TERM-2).

``GET /pronunciations?document_id=N`` lists one document's overrides (omit ``document_id`` for
the global lexicon); ``PUT /pronunciations`` stores one (``document_id`` null is global) and
returns the row plus ``invalidated``; ``DELETE /pronunciations/{id}`` returns ``invalidated``.
A change deletes the cached audio of every segment of the affected documents (one, or all for
a global change) whose ``normalized_text`` holds the word as a whole token, case-insensitively;
``invalidated`` is the number of ``audio_cache`` rows removed. SYN-6 keys stay by segment id.
"""

from __future__ import annotations

import asyncio
import re
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, field_validator

from hearnarro.routes.documents import Conn
from hearnarro.storage import repo
from hearnarro.storage.db import connect_sync, db_path

router = APIRouter()

WORD_MAX = 100
RESPELLING_MAX = 200


class PronunciationIn(BaseModel):
    document_id: int | None = None
    word: str = Field(max_length=WORD_MAX)
    respelling: str = Field(max_length=RESPELLING_MAX)

    @field_validator("word")
    @classmethod
    def _word(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("word must not be empty")
        return v.lower()

    @field_validator("respelling")
    @classmethod
    def _respelling(cls, v: str) -> str:
        v = v.strip()
        if not any(ch.isalpha() for ch in v):
            raise ValueError("respelling must contain a letter")
        return v


def _token_pattern(word: str) -> re.Pattern[str]:
    return re.compile(rf"(?<!\w){re.escape(word)}(?!\w)", re.IGNORECASE)


def segments_with_word(conn: Any, document_id: int | None, word: str) -> list[int]:
    """Ids of the segments of ``document_id`` (every document when None) whose
    ``normalized_text`` contains ``word`` as a whole token, case-insensitive."""
    sql = "SELECT id, normalized_text FROM segments WHERE 1 = 1"
    params: list[object] = []
    if document_id is not None:
        sql += " AND document_id = ?"
        params.append(document_id)
    if word.isascii():  # SQLite's LIKE folds ASCII case only; a prefilter, the regex decides
        escaped = word.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        sql += " AND normalized_text LIKE ? ESCAPE '\\'"
        params.append(f"%{escaped}%")
    pattern = _token_pattern(word)
    return [sid for sid, text in conn.execute(sql, params) if text and pattern.search(text)]


def _invalidate(data_dir: Path, document_id: int | None, word: str) -> int:
    from hearnarro.cli import purge_segments

    conn = connect_sync(db_path(data_dir))
    try:
        return purge_segments(conn, segments_with_word(conn, document_id, word), data_dir)
    finally:
        conn.close()


async def _after_change(request: Request, document_id: int | None, word: str) -> int:
    invalidated = await asyncio.to_thread(
        _invalidate, request.app.state.data_dir, document_id, word
    )
    service = getattr(request.app.state, "synthesis", None)
    if service is not None:
        service.invalidate_context(document_id)
    return invalidated


async def _document_or_404(conn: Conn, document_id: int | None) -> None:
    if document_id is not None and await repo.get_document(conn, document_id) is None:
        raise HTTPException(404, f"document {document_id} not found")


@router.get("/pronunciations")
async def list_pronunciations(conn: Conn, document_id: int | None = None) -> list[dict[str, Any]]:
    await _document_or_404(conn, document_id)
    return await repo.list_pronunciations(conn, document_id)


@router.put("/pronunciations")
async def put_pronunciation(body: PronunciationIn, request: Request, conn: Conn) -> dict[str, Any]:
    await _document_or_404(conn, body.document_id)
    row = await repo.put_pronunciation(conn, body.document_id, body.word, body.respelling)
    return {**row, "invalidated": await _after_change(request, body.document_id, row["word"])}


@router.delete("/pronunciations/{pronunciation_id}")
async def delete_pronunciation(
    pronunciation_id: int, request: Request, conn: Conn
) -> dict[str, int]:
    row = await repo.delete_pronunciation(conn, pronunciation_id)
    if row is None:
        raise HTTPException(404, f"pronunciation {pronunciation_id} not found")
    return {"invalidated": await _after_change(request, row["document_id"], row["word"])}
