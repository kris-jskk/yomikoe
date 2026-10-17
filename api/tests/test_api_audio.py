"""API contract for audio and voices (SYN-1, SYN-2, SYN-3, SYN-5, SYN-6; D5, D7).

httpx against a temp data dir with FakeBackend variants (``SpyBackend``) and WavEncoder:
miss then hit (second call faster, HEAD 200 after), headers, 404/422/502, the cache file on
disk, lookahead visible through HEAD, and ``/voices`` (>= 6 voices across both genders).
"""

from __future__ import annotations

import asyncio
import io
import json
import sqlite3
import time
import wave
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import httpx

from hearnarro.synthesis.encode import WavEncoder
from tests.conftest import SpyBackend
from tests.test_api_documents import REPORT_PDF, client_for, upload, wait_settled

VOICE = "fake_f2"
TS_KEYS = {"word", "start_ms", "end_ms", "char_start", "char_end"}


@asynccontextmanager
async def ready_document(
    tmp_path: Path, backend: SpyBackend | None = None, lookahead: int = 0
) -> AsyncIterator[tuple[httpx.AsyncClient, list[dict[str, Any]]]]:
    """App with ``backend`` (default SpyBackend()), WavEncoder and ``lookahead``; report_01
    uploaded and ready. Yields (client, segment rows in reading order)."""
    backend = backend if backend is not None else SpyBackend()
    async with client_for(
        tmp_path, tts_backend=backend, encoder=WavEncoder(), lookahead=lookahead
    ) as client:
        doc_id = (await upload(client, REPORT_PDF)).json()["id"]
        assert (await wait_settled(client, doc_id))["status"] == "ready"
        page = (await client.get(f"/documents/{doc_id}/segments?limit=500")).json()
        client.document_id = doc_id  # type: ignore[attr-defined]
        yield client, page["segments"]


def worded(segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [s for s in segments if s["normalized_text"].split()]


async def test_syn1_audio_get_miss_then_hit_headers_and_head(tmp_path: Path) -> None:
    spy = SpyBackend(delay_s=0.3)
    async with ready_document(tmp_path, spy) as (client, segments):
        seg = worded(segments)[0]
        url, params = f"/audio/{seg['id']}", {"voice": VOICE, "speed": 1.0}

        assert (await client.head(url, params=params)).status_code == 404

        t0 = time.perf_counter()
        miss = await client.get(url, params=params)
        t_miss = time.perf_counter() - t0
        assert miss.status_code == 200, miss.text
        assert miss.headers["content-type"].startswith("audio/wav")
        with wave.open(io.BytesIO(miss.content), "rb") as w:
            assert (w.getframerate(), w.getnchannels(), w.getsampwidth()) == (24_000, 1, 2)
            frames = w.getnframes()
        duration = int(miss.headers["x-duration-ms"])
        assert abs(duration - frames * 1000 / 24_000) <= 1
        ts = json.loads(miss.headers["x-timestamps"])
        assert isinstance(ts, list) and len(ts) == len(seg["normalized_text"].split())
        for t in ts:
            assert set(t) == TS_KEYS
            assert 0 <= t["char_start"] < t["char_end"] <= len(seg["text"])  # text offsets
        assert ts[-1]["end_ms"] <= duration

        head = await client.head(url, params=params)
        assert head.status_code == 200
        assert head.content == b""

        t0 = time.perf_counter()
        hit = await client.get(url, params=params)
        t_hit = time.perf_counter() - t0
        assert hit.status_code == 200
        assert hit.content == miss.content
        assert hit.headers["x-timestamps"] == miss.headers["x-timestamps"]
        assert hit.headers["x-duration-ms"] == miss.headers["x-duration-ms"]
        assert t_miss >= 0.3 > t_hit, (t_miss, t_hit)
        assert t_hit < t_miss
        assert len(spy.calls) == 1  # the hit never reached the backend


async def test_syn6_audio_cache_file_and_row_written(tmp_path: Path) -> None:
    async with ready_document(tmp_path) as (client, segments):
        seg = worded(segments)[1]
        resp = await client.get(f"/audio/{seg['id']}", params={"voice": VOICE, "speed": 1.5})
        assert resp.status_code == 200, resp.text
        doc_id = client.document_id  # type: ignore[attr-defined]
    path = tmp_path / "audio" / str(doc_id) / str(seg["id"]) / f"{VOICE}_1.5.wav"
    assert path.read_bytes() == resp.content
    assert not list((tmp_path / "audio").rglob("*.tmp"))
    db = sqlite3.connect(tmp_path / "hearnarro.db")
    try:
        rows = db.execute(
            "SELECT voice_id, speed, backend, status, duration_ms, timestamps_json "
            "FROM audio_cache WHERE segment_id = ?",
            (seg["id"],),
        ).fetchall()
    finally:
        db.close()
    assert len(rows) == 1
    voice, speed, backend, status, duration_ms, ts_json = rows[0]
    assert (voice, speed, backend, status) == (VOICE, 1.5, "fake", "ready")
    assert duration_ms == int(resp.headers["x-duration-ms"])
    assert json.loads(ts_json) == json.loads(resp.headers["x-timestamps"])


async def test_syn6_head_never_synthesizes(tmp_path: Path) -> None:
    spy = SpyBackend()
    async with ready_document(tmp_path, spy) as (client, segments):
        url = f"/audio/{worded(segments)[5]['id']}"
        for _ in range(2):
            resp = await client.head(url, params={"voice": VOICE, "speed": 1.0})
            assert resp.status_code == 404
            await asyncio.sleep(0.1)
        assert spy.calls == []


async def test_syn1_audio_unknown_segment_404(tmp_path: Path) -> None:
    async with ready_document(tmp_path) as (client, _):
        params = {"voice": VOICE, "speed": 1.0}
        assert (await client.get("/audio/999999", params=params)).status_code == 404
        assert (await client.head("/audio/999999", params=params)).status_code == 404


async def test_syn2_audio_unknown_or_missing_voice_422(tmp_path: Path) -> None:
    spy = SpyBackend()
    async with ready_document(tmp_path, spy) as (client, segments):
        url = f"/audio/{segments[0]['id']}"
        assert (await client.get(url, params={"voice": "af_heart", "speed": 1.0})).status_code == (
            422
        )
        assert (await client.get(url, params={"speed": 1.0})).status_code == 422
        assert (await client.get(url, params={"voice": VOICE})).status_code == 422
        assert spy.calls == []


async def test_syn1_audio_synthesis_failure_502_and_row_failed(tmp_path: Path) -> None:
    spy = SpyBackend(fail_texts={"*"})
    async with ready_document(tmp_path, spy) as (client, segments):
        sid = worded(segments)[0]["id"]
        params = {"voice": VOICE, "speed": 1.0}
        resp = await client.get(f"/audio/{sid}", params=params)
        assert resp.status_code == 502, resp.text
        body = resp.json()
        assert body["segment_id"] == sid
        assert isinstance(body["reason"], str) and body["reason"]
        assert (await client.head(f"/audio/{sid}", params=params)).status_code == 404
    db = sqlite3.connect(tmp_path / "hearnarro.db")
    try:
        status = db.execute(
            "SELECT status FROM audio_cache WHERE segment_id=? AND voice_id=? AND speed=? "
            "AND backend='fake'",
            (sid, VOICE, 1.0),
        ).fetchall()
    finally:
        db.close()
    assert status == [("failed",)]


async def test_syn5_audio_lookahead_visible_through_head(tmp_path: Path) -> None:
    async with ready_document(tmp_path, lookahead=3) as (client, segments):
        params = {"voice": VOICE, "speed": 1.0}
        assert (await client.get(f"/audio/{segments[0]['id']}", params=params)).status_code == 200
        ahead = [s["id"] for s in segments[1:4]]
        deadline = time.monotonic() + 5.0
        while True:
            codes = [(await client.head(f"/audio/{i}", params=params)).status_code for i in ahead]
            if codes == [200, 200, 200] or time.monotonic() > deadline:
                break
            await asyncio.sleep(0.05)
        assert codes == [200, 200, 200]
        await asyncio.sleep(0.2)
        beyond = await client.head(f"/audio/{segments[4]['id']}", params=params)
        assert beyond.status_code == 404


async def test_syn2_voices_six_across_both_genders(tmp_path: Path) -> None:
    async with client_for(tmp_path, tts_backend=SpyBackend(), encoder=WavEncoder()) as client:
        resp = await client.get("/voices")
    assert resp.status_code == 200, resp.text
    voices = resp.json()
    assert len(voices) >= 6
    assert {"female", "male"} <= {v["gender"] for v in voices}
    for v in voices:
        assert {"id", "name", "backend", "language", "gender"} <= set(v)
        assert v["language"]  # BCP-47 tag, e.g. en-US
    assert len({v["id"] for v in voices}) == len(voices)


async def test_syn1_audio_format_opus_serves_ogg_same_timestamps_d16(
    tmp_path: Path, monkeypatch: Any
) -> None:
    """HEARNARRO_AUDIO_FORMAT=opus: the encoder comes from settings; same X-Timestamps as WAV."""
    import pytest

    pytest.importorskip("opuscodec")
    async with ready_document(tmp_path / "wav") as (client, segments):
        seg = worded(segments)[0]
        params = {"voice": VOICE, "speed": 1.0}
        wav = await client.get(f"/audio/{seg['id']}", params=params)
        assert wav.status_code == 200 and wav.headers["content-type"].startswith("audio/wav")

    monkeypatch.setenv("HEARNARRO_AUDIO_FORMAT", "opus")
    monkeypatch.setenv("HEARNARRO_TTS_BACKEND", "fake")
    async with client_for(tmp_path / "ogg", tts_backend=SpyBackend(), lookahead=0) as client:
        doc_id = (await upload(client, REPORT_PDF)).json()["id"]
        assert (await wait_settled(client, doc_id))["status"] == "ready"
        page = (await client.get(f"/documents/{doc_id}/segments?limit=500")).json()
        seg2 = worded(page["segments"])[0]
        assert seg2["text"] == seg["text"]
        url = f"/audio/{seg2['id']}"
        ogg = await client.get(url, params=params)
        assert ogg.status_code == 200, ogg.text
        assert ogg.headers["content-type"].startswith("audio/ogg")
        assert ogg.content[:4] == b"OggS"
        assert len(ogg.content) < len(wav.content)
        assert ogg.headers["x-timestamps"] == wav.headers["x-timestamps"]
        assert ogg.headers["x-duration-ms"] == wav.headers["x-duration-ms"]
        head = await client.head(url, params=params)
        assert head.status_code == 200 and head.headers["content-type"].startswith("audio/ogg")
        files = list((tmp_path / "ogg").rglob("*.ogg"))
        assert files, "cache file should carry the .ogg extension"
