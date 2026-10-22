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
import shutil
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Annotated, Any, Literal

import aiosqlite
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from yomikoe.storage import repo
from yomikoe.storage.db import connect_sync, db_path, pdf_dir
from yomikoe.storage.jobs import run_ingestion

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


SPEED_MIN = 0.5  # LIB-3: the same bounds as PUT /settings
SPEED_MAX = 3.0


def _document_summary(doc: dict[str, Any]) -> dict[str, Any]:
    """The one summary shape (LIB-1) for GET /documents, GET /documents/{id} and PATCH.

    ``doc`` is a row from ``repo.list_document_summaries``/``get_document_summary``.
    ``progress`` = the position segment's ``order`` / ``segment_count``, 0 without a position.
    """
    keys = (
        "id",
        "title",
        "filename",
        "sha256",
        "page_count",
        "pages_done",
        "parse_ms",
        "status",
        "fail_reason",
        "created_at",
        "last_opened_at",
        "segment_count",
        "ocr_skipped_pages",
    )
    count = int(doc["segment_count"] or 0)
    order = doc["position_order"]
    has_position = doc["position_segment_id"] is not None and order is not None
    return {k: doc[k] for k in keys} | {
        "position": {
            "segment_id": doc["position_segment_id"] if has_position else None,
            "offset_ms": int(doc["position_offset_ms"] or 0) if has_position else 0,
        },
        "progress": order / count if has_position and count else 0,
        "settings": {"voice_id": doc["voice_id"], "speed": doc["speed"]},
        "profile": _profile_summary(doc),
    }


def _profile_summary(doc: dict[str, Any]) -> dict[str, Any]:
    """ING-11, LIB-1: the effective class, the computed one, the override and the raw shares."""
    p = repo.document_profile(doc)
    return {
        "class": p.effective,
        "computed_class": p.cls,
        "override": p.override,
        "math_share": p.math_share,
        "display_per_page": p.display_per_page,
        "inline_token_share": p.inline_token_share,
        "code_share": p.code_share,
        "citation_style": p.citation_style,
        "scanned_share": p.scanned_share,
        "author_year_citations": p.author_year_citations,
    }


class PositionIn(BaseModel):
    segment_id: int
    offset_ms: int = Field(default=0, ge=0)


class DocSettingsIn(BaseModel):
    voice_id: str | None = None
    speed: float | None = Field(default=None, ge=SPEED_MIN, le=SPEED_MAX)


class ProfileIn(BaseModel):
    """ING-11: ``class: null`` clears the override; an unknown class is a 422."""

    model_config = ConfigDict(populate_by_name=True)
    cls: Literal["prose", "mixed", "math"] | None = Field(default=None, alias="class")
    author_year_citations: Literal["read", "skip"] | None = None


class DocumentPatch(BaseModel):
    """Every key optional (LIB-2, LIB-3, D26, ING-11); ``position: null`` clears the position."""

    position: PositionIn | None = None
    settings: DocSettingsIn | None = None
    opened: bool | None = None
    profile: ProfileIn | None = None


async def _summary_or_404(conn: aiosqlite.Connection, document_id: int) -> dict[str, Any]:
    doc = await repo.get_document_summary(conn, document_id)
    if doc is None:
        raise HTTPException(404, "document not found")
    return doc


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
    return [_document_summary(d) for d in await repo.list_document_summaries(conn)]


@router.get("/documents/{document_id}")
async def get_document(document_id: int, conn: Conn) -> dict[str, Any]:
    doc = await _summary_or_404(conn, document_id)
    return _document_summary(doc) | {
        "sections": await repo.list_sections(conn, document_id),
        "acronyms": repo.document_acronyms(doc),
    }


@router.patch("/documents/{document_id}")
async def patch_document(
    document_id: int, body: DocumentPatch, request: Request, conn: Conn
) -> dict[str, Any]:
    """LIB-2/LIB-3: position, per-document settings, ``opened``; returns the summary.
    404 unknown document; 422 if the position segment is not one of the document's.

    ING-11 (D40): ``profile`` sets the class override and the TERM-3 toggle; when either
    changes, the stored segments are re-normalized through ``renormalize_document`` (the
    ``yomikoe renormalize`` path, no re-ingest) and the response carries
    ``renormalized: {changed, removed}``. 409 while the document is parsing."""
    doc = await _summary_or_404(conn, document_id)
    renormalized: dict[str, int] | None = None
    if body.profile is not None:
        if doc["status"] == "parsing":
            raise HTTPException(409, "document is still parsing")
        renormalized = await asyncio.to_thread(
            _apply_profile, request.app.state.data_dir, document_id, body.profile
        )
    sent = body.model_fields_set
    fields: dict[str, Any] = {}
    if "position" in sent:
        pos = body.position
        if pos is None:
            fields |= {"position_segment_id": None, "position_offset_ms": 0}
        else:
            if not await repo.segment_belongs(conn, document_id, pos.segment_id):
                raise HTTPException(422, "segment_id is not a segment of this document")
            fields |= {"position_segment_id": pos.segment_id, "position_offset_ms": pos.offset_ms}
    if "settings" in sent:
        st = body.settings
        if st is None:
            fields |= {"voice_id": None, "speed": None}
        else:
            if "voice_id" in st.model_fields_set:
                fields["voice_id"] = st.voice_id
            if "speed" in st.model_fields_set:
                fields["speed"] = st.speed
    if body.opened:
        fields["last_opened_at"] = repo.now_iso_ms()
    await repo.update_document_fields(conn, document_id, fields)
    summary = _document_summary(await _summary_or_404(conn, document_id))
    if renormalized is not None:
        summary["renormalized"] = renormalized
    return summary


def _apply_profile(data_dir: Path, document_id: int, body: ProfileIn) -> dict[str, int]:
    """Store the override on a sync connection and re-normalize if the profile changed."""
    from yomikoe.cli import renormalize_document

    sent = body.model_fields_set
    conn = connect_sync(db_path(data_dir))
    try:
        before = repo.get_document_profile(conn, document_id)
        cls = body.cls if "cls" in sent else before.override
        after = repo.set_profile_override(conn, document_id, cls, body.author_year_citations)
        if after == before:
            return {"changed": 0, "removed": 0}
        changed, removed, _ = renormalize_document(conn, document_id, data_dir)
    finally:
        conn.close()
    return {"changed": changed, "removed": removed}


@router.delete("/documents/{document_id}", status_code=204)
async def delete_document(document_id: int, request: Request, conn: Conn) -> Response:
    """LIB-4: rows, ``pdfs/{sha256}.pdf`` and ``audio/{id}/``; 404 unknown; 409 while parsing
    (status read from the documents row)."""
    doc = await _summary_or_404(conn, document_id)
    if doc["status"] == "parsing":
        raise HTTPException(409, "document is still parsing")
    await repo.delete_document(conn, document_id)
    data_dir: Path = request.app.state.data_dir
    pdf_path = pdf_dir(data_dir) / f"{doc['sha256']}.pdf"
    audio_dir = data_dir / "audio" / str(document_id)

    def remove_files() -> None:
        pdf_path.unlink(missing_ok=True)
        shutil.rmtree(audio_dir, ignore_errors=True)

    await asyncio.to_thread(remove_files)
    return Response(status_code=204)


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
