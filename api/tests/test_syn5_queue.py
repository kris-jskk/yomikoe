"""SYN-5 lookahead queue (and SYN-6 cache skip; D9 single synthesis thread).

Service-level, with SpyBackend (records calls; optional per-call delay), InMemoryCache and
MemorySegmentRepo over the ingested report_01 + academic_01 segments (ids are
``document_id * 10_000 + order``).
"""

from __future__ import annotations

import asyncio
import threading
import time

import pytest

from hearnarro.ingestion.models import Segment
from hearnarro.synthesis.cache import AudioEntry
from tests.conftest import SpyBackend, make_service, synth_fixture_segments

VOICE = "fake_f1"
SPEED = 1.0
DOC = 1


def doc_segments(document_id: int = DOC) -> list[Segment]:
    return sorted(
        (s for s in synth_fixture_segments() if s.document_id == document_id),
        key=lambda s: s.order,
    )


def at(order: int, document_id: int = DOC) -> Segment:
    return doc_segments(document_id)[order]


async def wait_for(predicate, timeout_s: float = 5.0) -> None:
    deadline = time.monotonic() + timeout_s
    while not predicate():
        assert time.monotonic() < deadline, "timed out"
        await asyncio.sleep(0.01)


@pytest.mark.parametrize("n", [3, 5])
async def test_syn5_lookahead_enqueues_n_after_first_request(n: int) -> None:
    service, spy, cache = make_service(lookahead=n)
    try:
        await service.get_audio(at(10).id, VOICE, SPEED)
        want = {at(10 + k).id for k in range(n + 1)}
        await wait_for(lambda: want <= cache.ready_ids())
        await wait_for(lambda: service.queue_depth(DOC) == 0)
        await asyncio.sleep(0.1)
        assert cache.ready_ids() == want  # exactly k..k+N, nothing beyond
        assert len(spy.calls) == n + 1
    finally:
        await service.shutdown()


async def test_syn5_lookahead_stops_at_document_end() -> None:
    segs = doc_segments()
    service, _, cache = make_service(lookahead=5)
    try:
        await service.get_audio(segs[-2].id, VOICE, SPEED)
        await wait_for(lambda: service.queue_depth(DOC) == 0)
        await asyncio.sleep(0.1)
        assert cache.ready_ids() == {segs[-2].id, segs[-1].id}  # never document 2
    finally:
        await service.shutdown()


async def test_syn5_lookahead_runs_on_single_synthesis_thread_off_the_loop() -> None:
    service, spy, cache = make_service(lookahead=5)
    try:
        await service.get_audio(at(0).id, VOICE, SPEED)
        await wait_for(lambda: len(cache.ready_ids()) == 6)
    finally:
        await service.shutdown()
    threads = {c[3] for c in spy.calls}
    assert len(threads) == 1  # D9: max_workers=1
    assert threading.main_thread().name not in threads


async def test_syn5_seek_clears_queue_and_refills_from_new_position() -> None:
    spy = SpyBackend(delay_s=0.1)
    service, _, cache = make_service(spy, lookahead=5)
    try:
        await service.get_audio(at(0).id, VOICE, SPEED)  # queues orders 1..5
        assert service.queue_depth(DOC) >= 1
        await service.prefetch(DOC, 30, VOICE, SPEED)
        assert service.queue_depth(DOC) <= 5
        want = {at(30 + k).id for k in range(5)}
        await wait_for(lambda: want <= cache.ready_ids())
        await wait_for(lambda: service.queue_depth(DOC) == 0)
    finally:
        await service.shutdown()
    # Assert by segment id (cache.ready_ids), not text: report_01 repeats its cover line
    # (orders 0/4 and 1/5 share normalized_text), so a text comparison hits the wrong segment.
    synthesized = cache.ready_ids()
    # at most the job in flight at the seek ran; the tail of the old window was dropped
    assert at(4).id not in synthesized
    assert at(5).id not in synthesized
    assert at(30).id in synthesized


async def test_syn5_voice_change_prefetch_uses_new_voice() -> None:
    service, spy, cache = make_service(lookahead=2)
    try:
        await service.prefetch(DOC, 0, "fake_m3", 1.5)
        await wait_for(lambda: service.queue_depth(DOC) == 0 and len(cache.ready_ids()) >= 2)
    finally:
        await service.shutdown()
    assert spy.calls and {(c[1], c[2]) for c in spy.calls} == {("fake_m3", 1.5)}


async def test_syn5_cached_jobs_skipped() -> None:
    service, spy, cache = make_service(lookahead=5)
    try:
        for order in (2, 3):
            seg = at(order)
            await cache.put(
                AudioEntry(seg.id, VOICE, SPEED, "fake", "ready", None, "audio/wav", 80, []),
                b"RIFF",
            )
        await service.get_audio(at(0).id, VOICE, SPEED)
        want = {at(k).id for k in range(6)}
        await wait_for(lambda: want <= cache.ready_ids())
        await wait_for(lambda: service.queue_depth(DOC) == 0)
    finally:
        await service.shutdown()
    texts = spy.texts
    assert at(2).normalized_text not in texts
    assert at(3).normalized_text not in texts
    assert len(texts) == 4  # orders 0, 1, 4, 5


async def test_syn6_cache_hit_returns_without_backend_call() -> None:
    service, spy, _ = make_service(lookahead=0)
    try:
        first = await service.get_audio(at(7).id, VOICE, SPEED)
        second = await service.get_audio(at(7).id, VOICE, SPEED)
    finally:
        await service.shutdown()
    assert len(spy.calls) == 1
    assert second.timestamps == first.timestamps
    assert second.duration_ms == first.duration_ms


async def test_syn5_first_request_jumps_the_queue() -> None:
    delay = 0.2
    spy = SpyBackend(delay_s=delay)
    service, _, cache = make_service(spy, lookahead=5)
    try:
        await service.prefetch(DOC, 0, VOICE, SPEED)  # five jobs ahead of us
        await asyncio.sleep(0.02)  # let the first one start
        t0 = time.perf_counter()
        entry = await service.get_audio(at(40).id, VOICE, SPEED)
        elapsed = time.perf_counter() - t0
    finally:
        await service.shutdown()
    assert entry.segment_id == at(40).id
    # in-flight job + this one, not the five queued before it
    assert elapsed < 3 * delay, elapsed
    # By id, not text: orders 0 and 4 share normalized_text in report_01, so the first
    # occurrence of that text is order 0. Order 4 (if it ran) is the second occurrence.
    texts = spy.texts
    cover = at(4).normalized_text
    assert cover == at(0).normalized_text  # documents the collision this test works around
    if at(4).id in cache.ready_ids():
        occurrences = [i for i, t in enumerate(texts) if t == cover]
        assert len(occurrences) >= 2
        assert texts.index(at(40).normalized_text) < occurrences[1]


async def test_syn5_failed_segment_raises_marks_failed_and_queue_moves_on() -> None:
    bad = at(2)
    spy = SpyBackend(fail_texts={bad.normalized_text})
    service, _, cache = make_service(spy, lookahead=4)
    try:
        await service.get_audio(at(0).id, VOICE, SPEED)
        want = {at(k).id for k in (0, 1, 3, 4)}
        await wait_for(lambda: want <= cache.ready_ids())
        assert cache.failures.keys() >= {(bad.id, VOICE, SPEED, "fake")}

        from hearnarro.synthesis.service import SegmentSynthesisFailed

        service2, _, cache2 = make_service(SpyBackend(fail_texts={"*"}), lookahead=0)
        try:
            with pytest.raises(SegmentSynthesisFailed) as info:
                await service2.get_audio(bad.id, VOICE, SPEED)
            assert info.value.segment_id == bad.id
            assert (bad.id, VOICE, SPEED, "fake") in cache2.failures
        finally:
            await service2.shutdown()
    finally:
        await service.shutdown()


async def test_syn5_shutdown_returns_within_5s_with_queue_full() -> None:
    service, _, _ = make_service(SpyBackend(delay_s=0.5), lookahead=5)
    await service.prefetch(DOC, 0, VOICE, SPEED)
    await asyncio.sleep(0.05)
    t0 = time.perf_counter()
    await service.shutdown()
    assert time.perf_counter() - t0 <= 5.0
    assert service.queue_depth(DOC) == 0
