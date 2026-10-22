"""M4 gate clause 1: the 300-page API soak (PRD "300-page soak"; LIB-4, ING-1, SYN-1).

Contract: ``_agent/specs/m4-library-interfaces.md`` sections 0 and 4. Runs only with
``YOMIKOE_TEST_SOAK=1`` (``@pytest.mark.soak``). A generated 300-page text PDF
(``tests/soak_util.py``) ingests to ``ready`` in under 300 s with peak RSS under 1.5 GB; every
segment page returns in order; ``/audio`` serves the first and the last segment with
``FakeBackend``; ``DELETE`` removes everything it created.

Ingestion runs in a ProcessPoolExecutor (D9), so peak RSS is reported for this process
(RUSAGE_SELF) and for the reaped pool workers (RUSAGE_CHILDREN, read after the app's lifespan
has shut the pool down); the gate is asserted on the larger of the two.
"""

from __future__ import annotations

import asyncio
import resource
import sqlite3
import sys
import time
from pathlib import Path

import pytest

from tests.soak_util import generate_soak_pdf
from tests.test_api_documents import client_for, upload
from yomikoe.synthesis.encode import WavEncoder
from yomikoe.synthesis.fake import FakeBackend

PAGES = 300
READY_LIMIT_S = 300.0
RSS_LIMIT_MB = 1536.0
POLL_DEADLINE_S = 600.0  # keep measuring past the gate so a miss still records its number
VOICE = "fake_f2"


def _maxrss_mb(who: int) -> float:
    raw = resource.getrusage(who).ru_maxrss
    return raw / (1024 * 1024) if sys.platform == "darwin" else raw / 1024  # bytes vs KiB


@pytest.mark.soak
async def test_soak_300_pages_ingest_page_audio_delete(tmp_path: Path) -> None:
    pdf = generate_soak_pdf(tmp_path / "soak_300.pdf", pages=PAGES)
    data_dir = tmp_path / "data"
    stats: dict[str, object] = {}

    async with client_for(data_dir, tts_backend=FakeBackend(), encoder=WavEncoder()) as client:
        t0 = time.perf_counter()
        resp = await upload(client, pdf)
        assert resp.status_code == 202, resp.text
        doc_id = resp.json()["id"]
        while True:
            body = (await client.get(f"/documents/{doc_id}")).json()
            if body["status"] in ("ready", "failed"):
                break
            assert time.perf_counter() - t0 < POLL_DEADLINE_S, body
            await asyncio.sleep(0.1)
        parse_s = time.perf_counter() - t0
        assert body["status"] == "ready", body
        stats.update(parse_s=parse_s, page_count=body.get("page_count"))
        stats["parse_ms_server"] = body.get("parse_ms")

        # every segment page, in order
        segments: list[dict[str, object]] = []
        start: int | None = 0
        t_pages = time.perf_counter()
        while start is not None:
            page = (await client.get(f"/documents/{doc_id}/segments?from={start}&limit=500")).json()
            assert [s["order"] for s in page["segments"]] == list(
                range(start, start + len(page["segments"]))
            )
            segments += page["segments"]
            start = page["next_from"]
        stats["paging_s"] = time.perf_counter() - t_pages
        assert len(segments) == page["total"]
        assert [s["order"] for s in segments] == list(range(len(segments)))
        stats["segments"] = len(segments)

        # /audio for the first and the last segment
        statuses = []
        for seg in (segments[0], segments[-1]):
            audio = await client.get(f"/audio/{seg['id']}", params={"voice": VOICE, "speed": 1.0})
            statuses.append(audio.status_code)
            assert audio.status_code == 200, audio.text
        stats["audio"] = statuses

        # DELETE removes everything it created
        sha = body["sha256"]
        assert (data_dir / "pdfs" / f"{sha}.pdf").exists()
        assert (await client.delete(f"/documents/{doc_id}")).status_code == 204
        assert (await client.get(f"/documents/{doc_id}")).status_code == 404
        assert (await client.get("/documents")).json() == []
        assert not (data_dir / "pdfs" / f"{sha}.pdf").exists()
        assert not (data_dir / "audio" / str(doc_id)).exists()

    db = sqlite3.connect(data_dir / "yomikoe.db")
    try:
        for table in ("blocks", "segments", "sections"):
            q = f"SELECT count(*) FROM {table} WHERE document_id = ?"
            assert db.execute(q, (doc_id,)).fetchone()[0] == 0, table
        assert db.execute("SELECT count(*) FROM audio_cache").fetchone()[0] == 0
    finally:
        db.close()

    rss_self = _maxrss_mb(resource.RUSAGE_SELF)
    rss_children = _maxrss_mb(resource.RUSAGE_CHILDREN)
    print(
        f"\nSOAK pages={stats['page_count']} segments={stats['segments']} "
        f"parse_wall_s={parse_s:.2f} parse_ms_server={stats['parse_ms_server']} "
        f"paging_s={stats['paging_s']:.2f} rss_self_mb={rss_self:.0f} "
        f"rss_children_mb={rss_children:.0f} audio_first_last={statuses}"
    )
    assert stats["page_count"] == PAGES
    assert parse_s < READY_LIMIT_S
    assert max(rss_self, rss_children) < RSS_LIMIT_MB
