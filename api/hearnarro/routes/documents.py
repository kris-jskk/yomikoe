"""Document endpoints (ING-1; documents, blocks, segments tables).

Status flow: the row is inserted as ``uploaded`` once the PDF is on disk, set to ``parsing``
just before the job is handed to the process pool (so the worker's ``ready``/``failed`` can
never be overwritten), and the handler returns 202 ``{id, status: "parsing"}`` without
waiting for the parse.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Annotated, Any

import aiosqlite
from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile
from fastapi.responses import JSONResponse

from hearnarro.storage import repo
from hearnarro.storage.db import db_path, pdf_dir
from hearnarro.storage.jobs import run_ingestion

log = logging.getLogger(__name__)
router = APIRouter()

SEGMENTS_DEFAULT_LIMIT = 100
SEGMENTS_MAX_LIMIT = 500  # larger limits are clamped, not rejected
CHUNK = 1024 * 1024
PDF_MAGIC = b"%PDF-"


async def get_conn(request: Request) -> AsyncIterator[aiosqlite.Connection]:
    async with request.app.state.engine.connect() as conn:
        yield conn


Conn = Annotated[aiosqlite.Connection, Depends(get_conn)]


def _document_summary(doc: dict[str, Any]) -> dict[str, Any]:
    keys = ("id", "title", "filename", "sha256", "page_count", "status", "fail_reason")
    return {k: doc[k] for k in keys} | {
        "created_at": doc["created_at"],
        "last_opened_at": doc["last_opened_at"],
    }


async def _read_capped(file: UploadFile, max_bytes: int) -> bytes:
    """Read the upload, 413 as soon as it exceeds ``max_bytes``."""
    parts: list[bytes] = []
    size = 0
    while chunk := await file.read(CHUNK):
        size += len(chunk)
        if size > max_bytes:
            raise HTTPException(413, f"PDF exceeds {max_bytes} bytes")
        parts.append(chunk)
    return b"".join(parts)


async def _watch_ingestion(request: Request, document_id: int, future: asyncio.Future) -> None:
    """Await the pool job; if the worker itself died, record the failure here."""
    state = request.app.state
    try:
        state.ingest_seconds[document_id] = await future
        log.info("ingested document %s in %.3fs", document_id, state.ingest_seconds[document_id])
    except asyncio.CancelledError:
        raise
    except Exception as exc:  # noqa: BLE001 - e.g. BrokenProcessPool
        async with state.engine.connect() as conn:
            await repo.set_status(conn, document_id, "failed", f"{type(exc).__name__}: {exc}")


@router.post("/documents", status_code=202)
async def upload_document(request: Request, file: UploadFile, conn: Conn) -> Any:
    """ING-1: 202 {id, status: parsing}; 200 with the existing id for the same bytes;
    415 if the body is not a PDF; 413 above the upload cap (100 MB)."""
    data = await _read_capped(file, request.app.state.max_upload_bytes)
    if PDF_MAGIC not in data[:1024]:
        raise HTTPException(415, "only PDF uploads are supported")
    sha256 = hashlib.sha256(data).hexdigest()

    existing = await repo.get_document_by_sha256(conn, sha256)
    if existing is not None:
        return JSONResponse({"id": existing["id"], "status": existing["status"]}, status_code=200)

    data_dir: Path = request.app.state.data_dir
    pdf_path = pdf_dir(data_dir) / f"{sha256}.pdf"
    await asyncio.to_thread(pdf_path.write_bytes, data)
    filename = Path(file.filename or "document.pdf").name
    try:
        doc_id = await repo.insert_document(
            conn, title=Path(filename).stem, filename=filename, sha256=sha256, status="uploaded"
        )
    except repo.DuplicateDocument:  # a concurrent upload of the same bytes won the insert
        existing = await repo.get_document_by_sha256(conn, sha256)
        assert existing is not None
        return JSONResponse({"id": existing["id"], "status": existing["status"]}, status_code=200)

    await repo.set_status(conn, doc_id, "parsing")
    loop = asyncio.get_running_loop()
    future = loop.run_in_executor(
        request.app.state.ingest_executor,
        run_ingestion,
        str(db_path(data_dir)),
        doc_id,
        str(pdf_path),
    )
    task = asyncio.create_task(_watch_ingestion(request, doc_id, future))
    request.app.state.ingest_tasks.add(task)
    task.add_done_callback(request.app.state.ingest_tasks.discard)
    return {"id": doc_id, "status": "parsing"}


@router.get("/documents")
async def list_documents(conn: Conn) -> list[dict[str, Any]]:
    return [_document_summary(d) for d in await repo.list_documents(conn)]


@router.get("/documents/{document_id}")
async def get_document(document_id: int, conn: Conn) -> dict[str, Any]:
    doc = await repo.get_document(conn, document_id)
    if doc is None:
        raise HTTPException(404, "document not found")
    return _document_summary(doc) | {
        "sections": await repo.list_sections(conn, document_id),
        "settings": {"voice_id": doc["voice_id"], "speed": doc["speed"]},
        "position": {
            "segment_id": doc["position_segment_id"],
            "offset_ms": doc["position_offset_ms"],
        },
    }


@router.get("/documents/{document_id}/segments")
async def get_segments(
    document_id: int,
    conn: Conn,
    from_: Annotated[int, Query(alias="from", ge=0)] = 0,
    limit: Annotated[int, Query(ge=1)] = SEGMENTS_DEFAULT_LIMIT,
) -> dict[str, Any]:
    """Segments with ``order >= from`` in reading order; ``limit`` is clamped to 500.
    ``next_from`` is the ``from`` of the next page, or null after the last one."""
    if await repo.get_document(conn, document_id) is None:
        raise HTTPException(404, "document not found")
    limit = min(limit, SEGMENTS_MAX_LIMIT)
    total = await repo.count_segments(conn, document_id)
    rows = await repo.list_segments(conn, document_id, from_, limit)
    end = rows[-1]["order"] + 1 if rows else from_
    return {
        "document_id": document_id,
        "total": total,
        "from": from_,
        "limit": limit,
        "next_from": end if end < total else None,
        "segments": rows,
    }
