"""Ingestion job run inside the ``ProcessPoolExecutor`` (D9; ING-1..ING-6).

``run_ingestion`` is module-level so it pickles by reference into a spawned worker. It
records ``page_count`` before extraction, updates ``pages_done`` while extracting (every 10
pages and the last, on its own connection), then writes every block and segment and flips
the document to ``ready`` in one transaction; any exception flips it to ``failed`` with the
message instead. Both outcomes set ``parse_ms``, the worker's wall time from job start.
"""

from __future__ import annotations

import json
import re
import sqlite3
import time
from collections.abc import Callable
from pathlib import Path

from hearnarro.ingestion.models import BBox
from hearnarro.ingestion.pipeline import IngestResult, ingest
from hearnarro.storage.db import connect_sync, pack_char_map

PROGRESS_EVERY = 10  # pages between pages_done writes (plus one write for the last page)


class PageProgress:
    """``on_page`` callback that calls ``write(pages_done)`` every ``every`` pages and at the end."""

    def __init__(self, write: Callable[[int], None], every: int = PROGRESS_EVERY) -> None:
        self.write = write
        self.every = every

    def __call__(self, done: int, total: int) -> None:
        if done % self.every == 0 or done == total:
            self.write(done)


def pdf_page_count(pdf_path: str | Path) -> int:
    import pypdfium2

    doc = pypdfium2.PdfDocument(str(pdf_path))
    try:
        return len(doc)
    finally:
        doc.close()


def _update(db_file: str | Path, sql: str, params: tuple[object, ...]) -> None:
    conn = connect_sync(db_file)
    try:
        with conn:
            conn.execute(sql, params)
    finally:
        conn.close()


def pdf_title(pdf_path: str | Path) -> str | None:
    """The PDF's Info-dictionary Title, or None when absent or blank."""
    import pypdfium2

    doc = pypdfium2.PdfDocument(str(pdf_path))
    try:
        title = (doc.get_metadata_dict().get("Title") or "").strip()
    finally:
        doc.close()
    return title or None


FILENAME_TITLE_RE = re.compile(r"\.(?:indd|docx?|pdf|tex|pages|qxd)$", re.IGNORECASE)
TITLE_HEADING_WORDS = (2, 12)


def _filename_like(title: str) -> bool:
    """A metadata Title that is really a file name ("Author_Book.indd") or a single token."""
    return bool(FILENAME_TITLE_RE.search(title)) or not any(c.isspace() for c in title)


def choose_title(meta_title: str | None, first_heading: str | None, filename: str) -> str:
    """The document title (found on a user book whose metadata Title is an InDesign file name).

    The PDF metadata Title unless it is missing, blank or filename-like; else the first
    heading when it has 2-12 words; else the filename stem with "-" and "_" as spaces.
    """
    meta = " ".join((meta_title or "").split())
    if meta and not _filename_like(meta):
        return meta
    heading = " ".join((first_heading or "").split())
    lo, hi = TITLE_HEADING_WORDS
    if lo <= len(heading.split()) <= hi:
        return heading
    stem = re.sub(r"[-_]+", " ", Path(filename).stem).strip()
    return " ".join(stem.split()) or Path(filename).stem


def _first_heading(result: IngestResult) -> str | None:
    return next((b.text for b in result.blocks if b.type == "heading" and b.text.strip()), None)


def _write_result(
    conn: sqlite3.Connection,
    document_id: int,
    result: IngestResult,
    title: str | None,
    parse_ms: int,
) -> None:
    """Blocks + segments + status in one transaction (``with conn`` commits or rolls back)."""
    raw_bbox: dict[tuple[int, int], BBox] = {
        (blk.page, blk.index): blk.bbox for page in result.pages for blk in page.blocks
    }
    with conn:
        conn.execute("DELETE FROM segments WHERE document_id = ?", (document_id,))
        conn.execute("DELETE FROM sections WHERE document_id = ?", (document_id,))
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
        # ING-8 / D25: one section per heading block that has segments (level 1 in v1);
        # each segment carries the latest section id (NULL before the first heading).
        heading_text = {b.id: b.text for b in result.blocks if b.type == "heading"}
        section_id: int | None = None
        sectioned: set[int] = set()
        for seg in sorted(result.segments, key=lambda s: s.order):
            new_section = seg.block_id in heading_text and seg.block_id not in sectioned
            if new_section:
                sectioned.add(seg.block_id)
                cur = conn.execute(
                    "INSERT INTO sections (document_id, title, level, first_segment_id) "
                    "VALUES (?, ?, 1, NULL)",
                    (document_id, heading_text[seg.block_id]),
                )
                section_id = cur.lastrowid
            cur = conn.execute(
                'INSERT INTO segments (document_id, block_id, section_id, "order", text, '
                "normalized_text, char_start, char_end, char_map) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    document_id,
                    block_ids[seg.block_id],
                    section_id,
                    seg.order,
                    seg.text,
                    seg.normalized_text,
                    seg.char_start,
                    seg.char_end,
                    pack_char_map(seg.char_map),
                ),
            )
            if new_section:
                conn.execute(
                    "UPDATE sections SET first_segment_id = ? WHERE id = ?",
                    (cur.lastrowid, section_id),
                )
        row = conn.execute("SELECT filename FROM documents WHERE id = ?", (document_id,)).fetchone()
        filename = row[0] if row and row[0] else "document.pdf"
        conn.execute(
            "UPDATE documents SET status = 'ready', fail_reason = NULL, page_count = ?, "
            "pages_done = ?, parse_ms = ?, title = ?, acronyms_json = ?, "
            "ocr_skipped_pages = ? WHERE id = ?",
            (
                len(result.pages),
                len(result.pages),
                parse_ms,
                choose_title(title, _first_heading(result), filename),
                json.dumps(result.acronyms, sort_keys=True),
                result.ocr_skipped_pages,
                document_id,
            ),
        )


def mark_failed(
    db_file: str | Path, document_id: int, reason: str, parse_ms: int | None = None
) -> None:
    _update(
        db_file,
        "UPDATE documents SET status = 'failed', fail_reason = ?, parse_ms = ? WHERE id = ?",
        (reason, parse_ms, document_id),
    )


def _elapsed_ms(start: float) -> int:
    return max(1, round((time.perf_counter() - start) * 1000))


def run_ingestion(db_file: str, document_id: int, pdf_path: str) -> float:
    """Parse ``pdf_path`` and store the result for ``document_id``. Returns wall seconds."""
    start = time.perf_counter()
    try:
        _update(
            db_file,
            "UPDATE documents SET page_count = ?, pages_done = 0, parse_ms = NULL WHERE id = ?",
            (pdf_page_count(pdf_path), document_id),
        )
        progress = PageProgress(
            lambda done: _update(
                db_file, "UPDATE documents SET pages_done = ? WHERE id = ?", (done, document_id)
            )
        )
        result = ingest(pdf_path, document_id=document_id, on_page=progress)
        title = pdf_title(pdf_path)
        conn = connect_sync(db_file)
        try:
            _write_result(conn, document_id, result, title, _elapsed_ms(start))
        finally:
            conn.close()
    except Exception as exc:  # noqa: BLE001 - any parse/store error becomes fail_reason
        mark_failed(db_file, document_id, f"{type(exc).__name__}: {exc}", _elapsed_ms(start))
    return time.perf_counter() - start
