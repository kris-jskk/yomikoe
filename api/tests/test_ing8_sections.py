"""ING-8: ingestion writes ``sections`` rows from heading blocks and sets ``segments.section_id``
(closes D25 for documents ingested after this lands).

Contract: ``_agent/specs/m4-library-interfaces.md`` section 1, "ING-8 sections": ``title`` =
heading block text, ``level`` = 1 in v1, ``first_segment_id`` = first segment of that block;
each segment after a heading carries the id of the latest section that starts at or before it.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from tests.conftest import SpyBackend
from tests.test_api_documents import REPORT_PDF, client_for, upload, wait_settled
from yomikoe.synthesis.encode import WavEncoder


async def _ingest_report(data_dir: Path) -> tuple[int, dict]:
    async with client_for(data_dir, tts_backend=SpyBackend(), encoder=WavEncoder()) as client:
        doc_id = (await upload(client, REPORT_PDF)).json()["id"]
        assert (await wait_settled(client, doc_id))["status"] == "ready"
        detail = (await client.get(f"/documents/{doc_id}")).json()
    return doc_id, detail


async def test_ing8_sections_rows_from_heading_blocks(tmp_path: Path) -> None:
    doc_id, detail = await _ingest_report(tmp_path)
    db = sqlite3.connect(tmp_path / "yomikoe.db")
    try:
        headings = db.execute(
            'SELECT b.merged_text, MIN(s."order"), (SELECT id FROM segments WHERE '
            'document_id = b.document_id AND block_id = b.id ORDER BY "order" LIMIT 1) '
            "FROM blocks b JOIN segments s ON s.block_id = b.id "
            "WHERE b.document_id = ? AND b.type = 'heading' GROUP BY b.id ORDER BY 2",
            (doc_id,),
        ).fetchall()
        sections = db.execute(
            "SELECT id, title, level, first_segment_id FROM sections "
            "WHERE document_id = ? ORDER BY id",
            (doc_id,),
        ).fetchall()
    finally:
        db.close()
    assert headings, "fixture must have heading blocks with segments"
    assert len(sections) == len(headings), (sections, headings)
    for (_sid, title, level, first_seg), (text, _order, first_id) in zip(
        sections, headings, strict=True
    ):
        assert title == text
        assert level == 1
        assert first_seg == first_id

    api_sections = detail["sections"]
    assert [s["title"] for s in api_sections] == [s[1] for s in sections]
    assert [s["first_segment_id"] for s in api_sections] == [s[3] for s in sections]


async def test_ing8_segments_carry_section_id(tmp_path: Path) -> None:
    doc_id, _detail = await _ingest_report(tmp_path)
    db = sqlite3.connect(tmp_path / "yomikoe.db")
    try:
        starts = db.execute(
            'SELECT sec.id, seg."order" FROM sections sec JOIN segments seg '
            "ON seg.id = sec.first_segment_id WHERE sec.document_id = ? ORDER BY 2",
            (doc_id,),
        ).fetchall()
        segs = db.execute(
            'SELECT "order", section_id FROM segments WHERE document_id = ? ORDER BY "order"',
            (doc_id,),
        ).fetchall()
    finally:
        db.close()
    assert starts, "no sections written"
    for order, section_id in segs:
        current = [sid for sid, start in starts if start <= order]
        expected = current[-1] if current else None
        assert section_id == expected, (order, section_id, expected)
