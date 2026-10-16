"""Ingestion job run inside the ``ProcessPoolExecutor`` (D9; ING-1..ING-6).

``run_ingestion`` is module-level so it pickles by reference into a spawned worker. It
parses the PDF, then writes every block and segment and flips the document to ``ready`` in
one transaction; any exception flips it to ``failed`` with the message instead.
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path

from hearnarro.ingestion.models import BBox
from hearnarro.ingestion.pipeline import IngestResult, ingest
from hearnarro.storage.db import connect_sync, pack_char_map


def pdf_title(pdf_path: str | Path) -> str | None:
    """The PDF's Info-dictionary Title, or None when absent or blank."""
    import pypdfium2

    doc = pypdfium2.PdfDocument(str(pdf_path))
    try:
        title = (doc.get_metadata_dict().get("Title") or "").strip()
    finally:
        doc.close()
    return title or None


def _write_result(
    conn: sqlite3.Connection, document_id: int, result: IngestResult, title: str | None
) -> None:
    """Blocks + segments + status in one transaction (``with conn`` commits or rolls back)."""
    raw_bbox: dict[tuple[int, int], BBox] = {
        (blk.page, blk.index): blk.bbox for page in result.pages for blk in page.blocks
    }
    with conn:
        conn.execute("DELETE FROM segments WHERE document_id = ?", (document_id,))
        conn.execute("DELETE FROM blocks WHERE document_id = ?", (document_id,))
        block_ids: dict[int, int] = {}
        for block in result.blocks:
            # bbox of the first source raw block; NULLs if that block is not found.
            bbox = raw_bbox.get(block.source[0]) if block.source else None
            coords = (bbox.x0, bbox.y0, bbox.x1, bbox.y1) if bbox else (None,) * 4
            cur = conn.execute(
                'INSERT INTO blocks (document_id, page, "order", type, x0, y0, x1, y1, '
                "merged_text) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (document_id, block.page, block.id, block.type, *coords, block.text),
            )
            assert cur.lastrowid is not None
            block_ids[block.id] = cur.lastrowid
        conn.executemany(
            'INSERT INTO segments (document_id, block_id, section_id, "order", text, '
            "normalized_text, char_start, char_end, char_map) "
            "VALUES (?, ?, NULL, ?, ?, ?, ?, ?, ?)",
            [
                (
                    document_id,
                    block_ids[seg.block_id],
                    seg.order,
                    seg.text,
                    seg.normalized_text,
                    seg.char_start,
                    seg.char_end,
                    pack_char_map(seg.char_map),
                )
                for seg in result.segments
            ],
        )
        conn.execute(
            "UPDATE documents SET status = 'ready', fail_reason = NULL, page_count = ?, "
            "title = COALESCE(?, title) WHERE id = ?",
            (len(result.pages), title, document_id),
        )


def mark_failed(db_file: str | Path, document_id: int, reason: str) -> None:
    conn = connect_sync(db_file)
    try:
        with conn:
            conn.execute(
                "UPDATE documents SET status = 'failed', fail_reason = ? WHERE id = ?",
                (reason, document_id),
            )
    finally:
        conn.close()


def run_ingestion(db_file: str, document_id: int, pdf_path: str) -> float:
    """Parse ``pdf_path`` and store the result for ``document_id``. Returns wall seconds."""
    start = time.perf_counter()
    try:
        result = ingest(pdf_path, document_id=document_id)
        title = pdf_title(pdf_path)
        conn = connect_sync(db_file)
        try:
            _write_result(conn, document_id, result, title)
        finally:
            conn.close()
    except Exception as exc:  # noqa: BLE001 - any parse/store error becomes fail_reason
        mark_failed(db_file, document_id, f"{type(exc).__name__}: {exc}")
    return time.perf_counter() - start
