"""API contract tests for the M1 skeleton (ING-1; documents, blocks, segments tables).

D11 "API contract" row: each endpoint via ``httpx.AsyncClient`` against a temp SQLite.
The app's lifespan (migrations + process pool) is entered explicitly because
``httpx.ASGITransport`` does not send lifespan events.

``yomikoe.app`` is imported inside the helpers, not at module level, so that before the
feature exists every test fails on its own instead of the module failing to collect.
"""

from __future__ import annotations

import asyncio
import sqlite3
import sys
import time
from array import array
from collections.abc import AsyncIterator
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import httpx
import pytest

from yomikoe.ingestion.pipeline import ingest

FIXTURES = Path(__file__).parent / "fixtures"
TEXT_PDF = FIXTURES / "unit" / "text.pdf"
REPORT_PDF = FIXTURES / "pdfs" / "report_01_zero_trust.pdf"
READY_TIMEOUT_S = 90.0


@asynccontextmanager
async def client_for(data_dir: Path, **kwargs: Any) -> AsyncIterator[httpx.AsyncClient]:
    from yomikoe.app import create_app

    app = create_app(data_dir, **kwargs)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            client.app = app  # type: ignore[attr-defined]
            yield client


async def upload(client: httpx.AsyncClient, path: Path, data: bytes | None = None):
    body = path.read_bytes() if data is None else data
    return await client.post("/documents", files={"file": (path.name, body, "application/pdf")})


async def wait_settled(client: httpx.AsyncClient, doc_id: int) -> dict[str, Any]:
    """Poll GET /documents/{id} until ready or failed (bounded)."""
    deadline = time.monotonic() + READY_TIMEOUT_S
    while True:
        resp = await client.get(f"/documents/{doc_id}")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        if body["status"] in ("ready", "failed"):
            return body
        assert time.monotonic() < deadline, f"document {doc_id} stuck in {body['status']}"
        await asyncio.sleep(0.05)


def unpack_char_map(blob: bytes) -> list[int]:
    arr = array("H")
    arr.frombytes(blob)
    if sys.byteorder == "big":
        arr.byteswap()
    return arr.tolist()


async def test_ing1_upload_returns_202_parsing_then_ready_documents_table(tmp_path: Path) -> None:
    async with client_for(tmp_path) as client:
        resp = await upload(client, TEXT_PDF)
        assert resp.status_code == 202, resp.text
        body = resp.json()
        assert isinstance(body["id"], int)
        assert body["status"] == "parsing"

        doc = await wait_settled(client, body["id"])
        assert doc["status"] == "ready", doc
        assert doc["fail_reason"] is None
        assert doc["page_count"] == 1
        # no PDF Title metadata -> the first heading ("Bold heading", 2-12 words)
        assert doc["title"] == "Bold heading"
        assert doc["filename"] == "text.pdf"
        assert len(doc["sha256"]) == 64
        assert (tmp_path / "pdfs" / f"{doc['sha256']}.pdf").read_bytes() == TEXT_PDF.read_bytes()

        listing = await client.get("/documents")
        assert listing.status_code == 200
        assert [d["id"] for d in listing.json()] == [body["id"]]


async def test_ing1_ingestion_uses_process_pool_of_two(tmp_path: Path) -> None:
    async with client_for(tmp_path) as client:
        pool = client.app.state.ingest_executor  # type: ignore[attr-defined]
        assert isinstance(pool, ProcessPoolExecutor)
        assert pool._max_workers == 2


async def test_ing1_ingestion_pool_uses_spawn_not_fork(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """D9: the pool must spawn, never fork. A worker forked while the API holds a SQLite
    connection inherits SQLite's per-inode lock state without the POSIX locks, and its
    writes fail with "disk I/O error" or corrupt the file (seen in Docker, Linux default
    start method fork; _agent/results/596_sqlite_hypotheses.txt)."""
    import multiprocessing.context as mpc

    # Make the process-wide default "fork" (as on Linux) so the test also bites on macOS.
    monkeypatch.setattr(mpc._default_context, "_actual_context", mpc._concrete_contexts["fork"])
    async with client_for(tmp_path) as client:
        pool = client.app.state.ingest_executor  # type: ignore[attr-defined]
        assert isinstance(pool._mp_context, mpc.SpawnContext)


async def test_ing1_reupload_same_bytes_dedupes_by_sha256_documents_table(tmp_path: Path) -> None:
    async with client_for(tmp_path) as client:
        first = await upload(client, TEXT_PDF)
        assert first.status_code == 202
        await wait_settled(client, first.json()["id"])
        again = await upload(client, TEXT_PDF)
        assert again.status_code == 200, again.text
        assert again.json()["id"] == first.json()["id"]
        assert again.json()["status"] == "ready"
        assert len((await client.get("/documents")).json()) == 1


async def test_ing1_segments_paging_segments_table(tmp_path: Path) -> None:
    expected = ingest(REPORT_PDF).segments
    assert len(expected) > 20
    async with client_for(tmp_path) as client:
        doc_id = (await upload(client, REPORT_PDF)).json()["id"]
        assert (await wait_settled(client, doc_id))["status"] == "ready"

        page1 = (await client.get(f"/documents/{doc_id}/segments?from=0&limit=20")).json()
        assert page1["total"] == len(expected)
        assert page1["next_from"] == 20
        rows = page1["segments"]
        assert [r["order"] for r in rows] == list(range(20))
        keys = {"id", "order", "block_id", "text", "normalized_text", "char_start", "char_end"}
        assert keys <= set(rows[0])
        assert [r["text"] for r in rows] == [s.text for s in expected[:20]]
        # each row carries its block's type so a client can apply the D12 prose-only filter
        result = ingest(REPORT_PDF)
        block_type = {b.id: b.type for b in result.blocks}
        assert [r["type"] for r in rows] == [block_type[s.block_id] for s in result.segments[:20]]

        page2 = (await client.get(f"/documents/{doc_id}/segments?from=20&limit=20")).json()
        assert [r["order"] for r in page2["segments"]] == list(range(20, 40))

        last = (await client.get(f"/documents/{doc_id}/segments?from=40&limit=20")).json()
        assert [r["order"] for r in last["segments"]] == list(range(40, len(expected)))
        assert last["next_from"] is None

        capped = (await client.get(f"/documents/{doc_id}/segments?from=0&limit=100000")).json()
        assert capped["limit"] == 500  # documented cap
        assert len(capped["segments"]) == len(expected)

        bad = await client.get(f"/documents/{doc_id}/segments?from=-1")
        assert bad.status_code == 422


async def test_ing1_report01_segments_match_ingest_blocks_segments_tables(tmp_path: Path) -> None:
    result = ingest(REPORT_PDF)
    async with client_for(tmp_path) as client:
        t0 = time.perf_counter()
        doc_id = (await upload(client, REPORT_PDF)).json()["id"]
        doc = await wait_settled(client, doc_id)
        elapsed = time.perf_counter() - t0
        print(f"\nINGEST_WALL report_01 upload->ready {elapsed:.3f}s")
        assert doc["status"] == "ready", doc
        assert doc["page_count"] == len(result.pages)

    db = sqlite3.connect(tmp_path / "yomikoe.db")
    try:
        n_blocks = db.execute("SELECT count(*) FROM blocks WHERE document_id=?", (doc_id,))
        assert n_blocks.fetchone()[0] == len(result.blocks)
        rows = db.execute(
            'SELECT "order", text, normalized_text, char_start, char_end, char_map '
            'FROM segments WHERE document_id=? ORDER BY "order"',
            (doc_id,),
        ).fetchall()
    finally:
        db.close()
    assert len(rows) == len(result.segments)
    assert [r[0] for r in rows] == list(range(len(result.segments)))
    for row, seg in zip(rows[:5], result.segments[:5], strict=True):
        assert row[1:5] == (seg.text, seg.normalized_text, seg.char_start, seg.char_end)
        assert unpack_char_map(row[5]) == seg.char_map


async def test_ing1_non_pdf_returns_415(tmp_path: Path) -> None:
    async with client_for(tmp_path) as client:
        resp = await client.post(
            "/documents", files={"file": ("notes.txt", b"just some text", "text/plain")}
        )
        assert resp.status_code == 415, resp.text
        assert (await client.get("/documents")).json() == []


async def test_ing1_pdf_over_limit_returns_413(tmp_path: Path) -> None:
    assert TEXT_PDF.stat().st_size > 1024
    async with client_for(tmp_path, max_upload_bytes=1024) as client:
        resp = await upload(client, TEXT_PDF)
        assert resp.status_code == 413, resp.text
        assert (await client.get("/documents")).json() == []


async def test_ing1_ingest_raises_sets_failed_documents_table(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from yomikoe.storage import jobs

    def boom(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("synthetic ingest failure")

    monkeypatch.setattr(jobs, "ingest", boom)
    # A monkeypatch does not cross a spawned process boundary, so this test swaps in a
    # thread executor; test_ing1_corrupt_pdf_fails_in_process_pool covers the real pool.
    async with client_for(tmp_path, executor_factory=lambda: ThreadPoolExecutor(1)) as client:
        doc_id = (await upload(client, TEXT_PDF)).json()["id"]
        doc = await wait_settled(client, doc_id)
        assert doc["status"] == "failed"
        assert "synthetic ingest failure" in doc["fail_reason"]


async def test_ing1_corrupt_pdf_fails_in_process_pool(tmp_path: Path) -> None:
    async with client_for(tmp_path) as client:
        resp = await upload(client, Path("broken.pdf"), b"%PDF-1.4\nthis is not a pdf body\n")
        assert resp.status_code == 202, resp.text
        doc = await wait_settled(client, resp.json()["id"])
        assert doc["status"] == "failed"
        assert doc["fail_reason"]


# --- parse progress and duration (pages_done, page_count, parse_ms; migration 0002) ---


async def test_ing1_parse_progress_pages_done_reaches_page_count_documents_table(
    tmp_path: Path,
) -> None:
    async with client_for(tmp_path) as client:
        doc_id = (await upload(client, REPORT_PDF)).json()["id"]
        seen: list[dict[str, Any]] = []
        deadline = time.monotonic() + READY_TIMEOUT_S
        while True:
            body = (await client.get(f"/documents/{doc_id}")).json()
            seen.append(body)
            if body["status"] in ("ready", "failed"):
                break
            assert time.monotonic() < deadline
            await asyncio.sleep(0.02)
        done = [b["pages_done"] for b in seen]
        assert done == sorted(done), done  # non-decreasing
        assert all(isinstance(d, int) and d >= 0 for d in done)
        for b in seen[:-1]:  # still parsing: no duration yet
            assert b["parse_ms"] in (None, 0), b
        final = seen[-1]
        assert final["status"] == "ready", final
        assert final["page_count"] == 4
        assert final["pages_done"] == final["page_count"]
        assert isinstance(final["parse_ms"], int) and final["parse_ms"] > 0

        (row,) = (await client.get("/documents")).json()
        assert row["pages_done"] == 4
        assert row["page_count"] == 4
        assert row["parse_ms"] == final["parse_ms"]


async def test_ing1_failed_document_carries_parse_ms_documents_table(tmp_path: Path) -> None:
    async with client_for(tmp_path) as client:
        resp = await upload(client, Path("broken.pdf"), b"%PDF-1.4\nthis is not a pdf body\n")
        doc = await wait_settled(client, resp.json()["id"])
        assert doc["status"] == "failed"
        assert isinstance(doc["parse_ms"], int) and doc["parse_ms"] >= 0
        assert doc["pages_done"] == 0


@pytest.mark.parametrize(
    ("total", "expected_writes"),
    [(242, 25), (4, 1), (10, 1), (11, 2), (30, 3), (1, 1)],
)
def test_ing1_page_progress_writes_every_10_pages_and_last(
    total: int, expected_writes: int
) -> None:
    from yomikoe.storage.jobs import PageProgress

    writes: list[int] = []
    progress = PageProgress(writes.append)
    for done in range(1, total + 1):
        progress(done, total)
    assert len(writes) == expected_writes, writes
    assert writes[-1] == total
    assert all(w % 10 == 0 for w in writes[:-1])


async def test_ing1_missing_document_returns_404(tmp_path: Path) -> None:
    async with client_for(tmp_path) as client:
        assert (await client.get("/documents/999")).status_code == 404
        assert (await client.get("/documents/999/segments")).status_code == 404


# --- title choice (found on a user book whose metadata Title is an InDesign file name) ---


@pytest.mark.parametrize(
    ("meta", "heading", "filename", "expected"),
    [
        ("The Almanack", "Other Heading Here", "x.pdf", "The Almanack"),
        (
            "Eric-Jorgenson_The-Almanack-of-Naval-Ravikant.indd",
            "THE ALMANACK OF NAVAL RAVIKANT",
            "book.pdf",
            "THE ALMANACK OF NAVAL RAVIKANT",
        ),
        ("draft.DOCX", "Two Words", "a.pdf", "Two Words"),
        ("Untitled", "Two Words", "a.pdf", "Two Words"),  # no whitespace: filename-like
        (None, "Two Words", "a.pdf", "Two Words"),
        ("  ", None, "my-great_book.pdf", "my great book"),
        (None, "Introduction", "my_book.pdf", "my book"),  # 1-word heading: too short
        (None, " ".join(["word"] * 13), "my_book.pdf", "my book"),  # 13 words: too long
    ],
)
def test_ing1_choose_title(
    meta: str | None, heading: str | None, filename: str, expected: str
) -> None:
    from yomikoe.storage.jobs import choose_title

    assert choose_title(meta, heading, filename) == expected


def _pdf_with_title(meta_title: str) -> bytes:
    """A one-page PDF with an Info Title, an 18 pt heading and 10 pt body lines."""
    lines = ["BT /F1 18 Tf 72 720 Td (A Guide to Listening) Tj ET"]
    for i in range(12):
        lines.append(
            f"BT /F1 10 Tf 72 {690 - 14 * i} Td "
            "(This is an ordinary line of body text in the main size.) Tj ET"
        )
    stream = "\n".join(lines).encode()
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>"
        ),
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Title (" + meta_title.encode() + b") >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for n, body in enumerate(objs, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % n + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    out += b"".join(b"%010d 00000 n \n" % o for o in offsets)
    out += b"trailer\n<< /Size %d /Root 1 0 R /Info 6 0 R >>\n" % (len(objs) + 1)
    out += b"startxref\n%d\n%%%%EOF\n" % xref
    return bytes(out)


async def test_ing1_filename_like_metadata_title_falls_back_to_first_heading(
    tmp_path: Path,
) -> None:
    pdf = tmp_path / "Some-Author_Some-Book.pdf"
    pdf.write_bytes(_pdf_with_title("Some-Author_Some-Book.indd"))
    async with client_for(tmp_path / "data") as client:
        resp = await upload(client, pdf)
        doc = await wait_settled(client, resp.json()["id"])
        assert doc["status"] == "ready", doc
        assert doc["title"] == "A Guide to Listening"
