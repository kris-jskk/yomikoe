"""MATH-5: ``GET /documents/{id}/segments`` rows carry ``math``, the sentence-level maths
ranges decoded from ``segments.math_json`` as ``[{start, end, display}]`` (offsets into the
row's ``text``), ``[]`` when the column is NULL.

Spec ``_agent/specs/m5-academic-reading.md`` section 4d ("MATH-5 at sentence level").
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from tests.test_api_documents import client_for, upload, wait_settled
from yomikoe.storage.db import connect_sync, db_path

PDFS = Path(__file__).parent / "fixtures" / "pdfs"
FORMULA_PDF = PDFS / "formula_01_pfn_bayes.pdf"
ACADEMIC_PDF = PDFS / "academic_01_seahelm_audio.pdf"


async def _all_segments(client: Any, doc_id: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    start: int | None = 0
    while start is not None:
        page = (await client.get(f"/documents/{doc_id}/segments?from={start}&limit=500")).json()
        rows.extend(page["segments"])
        start = page["next_from"]
    return rows


async def _ingest(client: Any, pdf: Path) -> int:
    resp = await upload(client, pdf)
    assert resp.status_code in (200, 202), resp.text
    doc_id = resp.json()["id"]
    assert (await wait_settled(client, doc_id))["status"] == "ready"
    return int(doc_id)


async def test_math5_formula_segments_carry_math_ranges_into_text(tmp_path: Path) -> None:
    async with client_for(tmp_path) as client:
        doc_id = await _ingest(client, FORMULA_PDF)
        rows = await _all_segments(client, doc_id)
    assert rows and all(isinstance(r["math"], list) for r in rows)
    with_math = [r for r in rows if r["math"]]
    assert with_math, "formula_01 has no segment with maths ranges"
    for row in with_math:
        for rng in row["math"]:
            assert set(rng) == {"start", "end", "display"}
            assert isinstance(rng["start"], int) and isinstance(rng["end"], int)
            assert isinstance(rng["display"], bool)
            assert 0 <= rng["start"] < rng["end"] <= len(row["text"])
            assert row["text"][rng["start"] : rng["end"]].strip()
    with connect_sync(db_path(tmp_path)) as conn:
        stored = conn.execute(
            "SELECT count(*) FROM segments WHERE document_id = ? AND math_json IS NOT NULL",
            (doc_id,),
        ).fetchone()[0]
    assert stored > 0


async def test_math5_prose_segment_of_academic_01_has_empty_math(tmp_path: Path) -> None:
    async with client_for(tmp_path) as client:
        doc_id = await _ingest(client, ACADEMIC_PDF)
        rows = await _all_segments(client, doc_id)
    assert all(isinstance(r["math"], list) for r in rows)
    prose = [
        r
        for r in rows
        if r["type"] == "body" and r["text"].replace(" ", "").replace(",", "").rstrip(".").isalpha()
    ]
    assert prose, "academic_01 has no plain prose segment"
    assert all(r["math"] == [] for r in prose)
