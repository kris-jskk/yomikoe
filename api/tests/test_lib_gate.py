"""M4 library gate, server half (LIB-1, LIB-2, LIB-3, LIB-4; D26).

Contract: ``_agent/specs/m4-library-interfaces.md`` section 1. httpx against a temp data dir
with ``SpyBackend`` (FakeBackend) and ``WavEncoder``, as in ``test_api_audio.py``:

- LIB-1: ``GET /documents`` summary carries ``segment_count``, ``position``, ``progress``
  (position segment's ``order`` / ``segment_count``, 0 without a position), ``settings`` and
  ``last_opened_at``; ``GET /documents/{id}`` carries ``segment_count``.
- LIB-2: ``PATCH /documents/{id}`` with ``position`` round-trips; 422 for a segment of another
  document; 404 for an unknown document; ``opened: true`` sets ``last_opened_at``.
- LIB-3: per-document ``settings`` through the same PATCH; ``GET``/``PUT /settings`` with
  ``default_speed`` 1.25 when unset and speed bounds [0.5, 3.0].
- LIB-4: ``DELETE /documents/{id}`` removes rows, the PDF and the audio directory; 404 unknown;
  409 while the document is still parsing.
"""

from __future__ import annotations

import asyncio
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

from hearnarro.synthesis.encode import WavEncoder
from tests.conftest import SpyBackend
from tests.test_api_audio import ready_document, worded
from tests.test_api_documents import TEXT_PDF, client_for, upload, wait_settled

VOICE = "fake_f2"


async def _summary(client: Any, doc_id: int) -> dict[str, Any]:
    rows = (await client.get("/documents")).json()
    (row,) = [r for r in rows if r["id"] == doc_id]
    return row


# --- LIB-1 library list -------------------------------------------------------------------


async def test_lib1_summary_fields_and_zero_progress_without_position(tmp_path: Path) -> None:
    async with ready_document(tmp_path) as (client, segments):
        doc_id = client.document_id  # type: ignore[attr-defined]
        row = await _summary(client, doc_id)
        assert row["segment_count"] == len(segments)
        assert row["progress"] == 0
        assert row["position"] is None or row["position"]["segment_id"] is None
        assert row["settings"] == {"voice_id": None, "speed": None}
        assert row["last_opened_at"] is None

        detail = (await client.get(f"/documents/{doc_id}")).json()
        assert detail["segment_count"] == len(segments)


async def test_lib1_progress_is_position_order_over_segment_count(tmp_path: Path) -> None:
    async with ready_document(tmp_path) as (client, segments):
        doc_id = client.document_id  # type: ignore[attr-defined]
        seg = segments[len(segments) // 2]
        resp = await client.patch(
            f"/documents/{doc_id}", json={"position": {"segment_id": seg["id"], "offset_ms": 0}}
        )
        assert resp.status_code == 200, resp.text
        row = await _summary(client, doc_id)
        assert row["progress"] == pytest.approx(seg["order"] / len(segments))
        assert 0 < row["progress"] < 1


# --- LIB-2 position persistence -------------------------------------------------------------


async def test_lib2_patch_position_round_trip(tmp_path: Path) -> None:
    async with ready_document(tmp_path) as (client, segments):
        doc_id = client.document_id  # type: ignore[attr-defined]
        seg = worded(segments)[3]
        body = {"position": {"segment_id": seg["id"], "offset_ms": 1234}}
        resp = await client.patch(f"/documents/{doc_id}", json=body)
        assert resp.status_code == 200, resp.text
        assert resp.json()["position"] == {"segment_id": seg["id"], "offset_ms": 1234}
        row = await _summary(client, doc_id)
        assert row["position"] == {"segment_id": seg["id"], "offset_ms": 1234}

        cleared = await client.patch(f"/documents/{doc_id}", json={"position": None})
        assert cleared.status_code == 200, cleared.text
        assert (await _summary(client, doc_id))["progress"] == 0


async def test_lib2_patch_foreign_segment_returns_422(tmp_path: Path) -> None:
    async with ready_document(tmp_path) as (client, _segments):
        doc_id = client.document_id  # type: ignore[attr-defined]
        other_id = (await upload(client, TEXT_PDF)).json()["id"]
        assert (await wait_settled(client, other_id))["status"] == "ready"
        other = (await client.get(f"/documents/{other_id}/segments")).json()["segments"]
        body = {"position": {"segment_id": other[0]["id"], "offset_ms": 0}}
        resp = await client.patch(f"/documents/{doc_id}", json=body)
        assert resp.status_code == 422, resp.text


async def test_lib2_patch_unknown_document_returns_404(tmp_path: Path) -> None:
    async with client_for(tmp_path, tts_backend=SpyBackend(), encoder=WavEncoder()) as client:
        resp = await client.patch("/documents/999", json={"opened": True})
        assert resp.status_code == 404, resp.text


async def test_lib2_opened_true_sets_last_opened_at(tmp_path: Path) -> None:
    async with ready_document(tmp_path) as (client, _segments):
        doc_id = client.document_id  # type: ignore[attr-defined]
        first = await client.patch(f"/documents/{doc_id}", json={"opened": True})
        assert first.status_code == 200, first.text
        t1 = first.json()["last_opened_at"]
        assert t1 is not None
        datetime.fromisoformat(t1)
        await asyncio.sleep(0.01)
        second = (await client.patch(f"/documents/{doc_id}", json={"opened": True})).json()
        assert datetime.fromisoformat(second["last_opened_at"]) >= datetime.fromisoformat(t1)
        assert (await _summary(client, doc_id))["last_opened_at"] == second["last_opened_at"]


# --- LIB-3 remembered voice and speed, global default ---------------------------------------


async def test_lib3_document_settings_set_and_clear(tmp_path: Path) -> None:
    async with ready_document(tmp_path) as (client, _segments):
        doc_id = client.document_id  # type: ignore[attr-defined]
        body = {"settings": {"voice_id": VOICE, "speed": 1.5}}
        resp = await client.patch(f"/documents/{doc_id}", json=body)
        assert resp.status_code == 200, resp.text
        assert resp.json()["settings"] == {"voice_id": VOICE, "speed": 1.5}
        assert (await _summary(client, doc_id))["settings"] == {"voice_id": VOICE, "speed": 1.5}

        cleared = await client.patch(
            f"/documents/{doc_id}", json={"settings": {"voice_id": None, "speed": None}}
        )
        assert cleared.status_code == 200, cleared.text
        assert cleared.json()["settings"] == {"voice_id": None, "speed": None}


async def test_lib3_global_settings_default_put_and_persist(tmp_path: Path) -> None:
    kwargs: dict[str, Any] = {"tts_backend": SpyBackend(), "encoder": WavEncoder()}
    async with client_for(tmp_path, **kwargs) as client:
        resp = await client.get("/settings")
        assert resp.status_code == 200, resp.text
        assert resp.json() == {"default_voice_id": None, "default_speed": 1.25}
        put = await client.put("/settings", json={"default_voice_id": VOICE, "default_speed": 1.5})
        assert put.status_code == 200, put.text
        assert (await client.get("/settings")).json() == {
            "default_voice_id": VOICE,
            "default_speed": 1.5,
        }
    async with client_for(tmp_path, **kwargs) as client:  # survives a restart
        assert (await client.get("/settings")).json()["default_speed"] == 1.5


@pytest.mark.parametrize(("speed", "status"), [(0.4, 422), (3.1, 422), (0.5, 200), (3.0, 200)])
async def test_lib3_global_settings_speed_bounds(tmp_path: Path, speed: float, status: int) -> None:
    async with client_for(tmp_path, tts_backend=SpyBackend(), encoder=WavEncoder()) as client:
        resp = await client.put(
            "/settings", json={"default_voice_id": None, "default_speed": speed}
        )
        assert resp.status_code == status, resp.text
        expected = speed if status == 200 else 1.25
        assert (await client.get("/settings")).json()["default_speed"] == expected


# --- LIB-4 delete ---------------------------------------------------------------------------


async def test_lib4_delete_removes_rows_pdf_and_audio_dir(tmp_path: Path) -> None:
    async with ready_document(tmp_path) as (client, segments):
        doc_id = client.document_id  # type: ignore[attr-defined]
        sha = (await client.get(f"/documents/{doc_id}")).json()["sha256"]
        seg = worded(segments)[0]
        audio = await client.get(f"/audio/{seg['id']}", params={"voice": VOICE, "speed": 1.0})
        assert audio.status_code == 200, audio.text
        pdf = tmp_path / "pdfs" / f"{sha}.pdf"
        audio_dir = tmp_path / "audio" / str(doc_id)
        assert pdf.exists() and audio_dir.exists()

        resp = await client.delete(f"/documents/{doc_id}")
        assert resp.status_code == 204, resp.text
        assert (await client.get(f"/documents/{doc_id}")).status_code == 404
        assert (await client.get("/documents")).json() == []
        assert not pdf.exists()
        assert not audio_dir.exists()

    db = sqlite3.connect(tmp_path / "hearnarro.db")
    try:
        for table in ("blocks", "segments", "sections"):
            q = f"SELECT count(*) FROM {table} WHERE document_id = ?"
            assert db.execute(q, (doc_id,)).fetchone()[0] == 0, table
        assert db.execute("SELECT count(*) FROM audio_cache").fetchone()[0] == 0
    finally:
        db.close()


async def test_lib4_delete_unknown_document_returns_404(tmp_path: Path) -> None:
    async with client_for(tmp_path, tts_backend=SpyBackend(), encoder=WavEncoder()) as client:
        resp = await client.delete("/documents/999")
        assert resp.status_code == 404, resp.text


async def test_lib4_delete_while_parsing_returns_409(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from hearnarro.storage import jobs

    release = threading.Event()
    real_ingest = jobs.ingest

    def slow_ingest(*args: Any, **kwargs: Any) -> Any:
        release.wait(timeout=60)
        return real_ingest(*args, **kwargs)

    monkeypatch.setattr(jobs, "ingest", slow_ingest)
    async with client_for(
        tmp_path,
        executor_factory=lambda: ThreadPoolExecutor(1),
        tts_backend=SpyBackend(),
        encoder=WavEncoder(),
    ) as client:
        try:
            doc_id = (await upload(client, TEXT_PDF)).json()["id"]
            assert (await client.get(f"/documents/{doc_id}")).json()["status"] == "parsing"
            resp = await client.delete(f"/documents/{doc_id}")
            assert resp.status_code == 409, resp.text
        finally:
            release.set()
        assert (await wait_settled(client, doc_id))["status"] == "ready"
        assert (await client.delete(f"/documents/{doc_id}")).status_code == 204
