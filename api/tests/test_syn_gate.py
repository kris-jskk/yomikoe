"""M2 gate (PRD M2): first audio within 2 s at 0.5x-3x on CPU (SYN-1, SYN-3, SYN-4).

Two forms of one contract:
- FakeBackend form (always runs): through the API on a cold cache, ``GET /audio`` for a
  real segment at 0.5/1.0/2.0/3.0 answers 200 with audio and timestamps within 2000 ms.
- Kokoro form (``@pytest.mark.model``, skipped unless ``HEARNARRO_TEST_MODEL=1``): TTFA
  <= 2000 ms on a 150-character sentence at the same speeds, plus the backend smoke test.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path

import pytest

from tests.conftest import InMemoryCache, make_service

GATE_SPEEDS = (0.5, 1.0, 2.0, 3.0)
TTFA_MS = 2000
SENTENCE_150 = (
    "Zero trust assumes there is no implicit trust granted to assets or user accounts "
    "based solely on their physical or network location, as NIST explains."
)

requires_model = pytest.mark.skipif(
    os.environ.get("HEARNARRO_TEST_MODEL") != "1", reason="set HEARNARRO_TEST_MODEL=1"
)


def test_syn_gate_sentence_is_150_chars() -> None:
    assert len(SENTENCE_150) == 150


async def test_syn_gate_fake_ttfa_under_2s_all_speeds(tmp_path: Path) -> None:
    from tests.test_api_audio import ready_document, worded

    async with ready_document(tmp_path, lookahead=5) as (client, segments):
        seg = worded(segments)[0]
        for speed in GATE_SPEEDS:  # each speed is a distinct cache key: cold every time
            t0 = time.perf_counter()
            resp = await client.get(
                f"/audio/{seg['id']}", params={"voice": "fake_f1", "speed": speed}
            )
            ttfa_ms = (time.perf_counter() - t0) * 1000
            print(f"\nTTFA fake speed={speed} {ttfa_ms:.0f} ms")
            assert resp.status_code == 200, resp.text
            assert len(resp.content) > 44
            assert json.loads(resp.headers["x-timestamps"])
            assert ttfa_ms <= TTFA_MS


@pytest.mark.model
@requires_model
def test_syn4_kokoro_smoke_one_sentence() -> None:
    from hearnarro.settings import load_settings
    from hearnarro.synthesis.kokoro_backend import KokoroBackend

    revision = load_settings().kokoro_revision
    assert revision, "HEARNARRO_KOKORO_REVISION must be set for the model tests"
    backend = KokoroBackend(revision=revision)
    voice = backend.voices()[0].id
    result = backend.synthesize("Zero trust is a security model.", voice, 1.0)
    assert result.duration_ms > 300
    assert result.timestamps


@pytest.mark.model
@requires_model
async def test_syn_gate_kokoro_ttfa_under_2s_150_chars() -> None:
    from hearnarro.ingestion.models import Segment
    from hearnarro.ingestion.normalize import normalize
    from hearnarro.settings import load_settings
    from hearnarro.synthesis.kokoro_backend import KokoroBackend

    revision = load_settings().kokoro_revision
    assert revision, "HEARNARRO_KOKORO_REVISION must be set for the model tests"
    backend = KokoroBackend(revision=revision)
    voice = backend.voices()[0].id
    await asyncio.to_thread(backend.synthesize, "Warm up.", voice, 1.0)  # warm model
    normalized, char_map = normalize(SENTENCE_150)
    seg = Segment(1, 1, 1, 0, None, SENTENCE_150, normalized, 0, 150, char_map)
    for speed in GATE_SPEEDS:
        service, _, _ = make_service(backend, segments=[seg], cache=InMemoryCache())
        try:
            t0 = time.perf_counter()
            entry = await service.get_audio(seg.id, voice, speed)
            ttfa_ms = (time.perf_counter() - t0) * 1000
        finally:
            await service.shutdown()
        print(f"\nTTFA kokoro speed={speed} {ttfa_ms:.0f} ms")
        assert entry.timestamps
        assert ttfa_ms <= TTFA_MS
