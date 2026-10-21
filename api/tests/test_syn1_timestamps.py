"""SYN-1 timestamp invariants over 50 fixture sentences (FakeBackend + SynthesisService).

Sentences are the first 25 worded segments of report_01 and academic_01 from ``ingest()``.
For each: timestamps sorted, non-overlapping in time, last end_ms <= duration_ms, every
(char_start, char_end) inside ``Segment.text`` (the service translates the backend's
normalized_text offsets through ``char_map``). The same holds on the stretched path (D6).
"""

from __future__ import annotations

import itertools

import pytest

from tests.conftest import fifty_fixture_sentences, make_service
from yomikoe.ingestion.models import Segment
from yomikoe.synthesis.backend import WordTimestamp
from yomikoe.synthesis.cache import AudioEntry
from yomikoe.synthesis.fake import FakeBackend

VOICE = "fake_f1"


def assert_timestamp_invariants(entry: AudioEntry, seg: Segment) -> None:
    ts = entry.timestamps
    assert ts, f"segment {seg.id}: no timestamps"
    assert len(ts) == len(seg.normalized_text.split())  # FakeBackend: one per word
    for t in ts:
        assert 0 <= t.start_ms <= t.end_ms, t
        assert 0 <= t.char_start < t.char_end <= len(seg.text), (t, seg.text)
    for a, b in itertools.pairwise(ts):
        assert a.start_ms <= b.start_ms, "not sorted"
        assert a.end_ms <= b.start_ms, "overlap in time"
        assert a.char_start <= b.char_start, "char spans out of order"
    assert ts[-1].end_ms <= entry.duration_ms


def expected_text_spans(seg: Segment, speed: float) -> list[tuple[int, int]]:
    """FakeBackend's normalized_text spans mapped through char_map: start -> char_map[start],
    end -> char_map[end - 1] + 1."""
    result = FakeBackend().synthesize(seg.normalized_text, VOICE, min(speed, 2.0))
    return [
        (seg.char_map[t.char_start], seg.char_map[t.char_end - 1] + 1) for t in result.timestamps
    ]


def test_syn1_fixture_sentences_are_fifty_and_some_are_normalized() -> None:
    segs = fifty_fixture_sentences()
    assert len(segs) == 50
    assert len({s.document_id for s in segs}) == 2
    assert any(s.text != s.normalized_text for s in segs)  # char_map is exercised


@pytest.mark.parametrize("speed", [1.0, 2.0])
async def test_syn1_timestamp_invariants_native_50_sentences(speed: float) -> None:
    service, _, _ = make_service()
    try:
        for seg in fifty_fixture_sentences():
            entry = await service.get_audio(seg.id, VOICE, speed)
            assert entry.status == "ready"
            assert_timestamp_invariants(entry, seg)
    finally:
        await service.shutdown()


@pytest.mark.parametrize("speed", [2.5, 3.0])
async def test_syn1_timestamp_invariants_stretched_50_sentences(speed: float) -> None:
    service, _, _ = make_service()
    try:
        for seg in fifty_fixture_sentences():
            entry = await service.get_audio(seg.id, VOICE, speed)
            assert entry.status == "ready"
            assert_timestamp_invariants(entry, seg)
    finally:
        await service.shutdown()


async def test_syn1_timestamps_translated_to_text_offsets_through_char_map() -> None:
    segs = fifty_fixture_sentences()
    service, _, _ = make_service()
    try:
        for seg in segs:
            entry = await service.get_audio(seg.id, VOICE, 1.0)
            got = [(t.char_start, t.char_end) for t in entry.timestamps]
            assert got == expected_text_spans(seg, 1.0), seg.text
    finally:
        await service.shutdown()


def test_syn1_scaled_timestamps_keep_invariants() -> None:
    from yomikoe.synthesis.stretch import scale_timestamps

    for seg in fifty_fixture_sentences():
        native = FakeBackend().synthesize(seg.normalized_text, VOICE, 2.0)
        for ratio in (1.05, 1.25, 1.5):
            scaled: list[WordTimestamp] = scale_timestamps(native.timestamps, ratio)
            assert len(scaled) == len(native.timestamps)
            for a, b in itertools.pairwise(scaled):
                assert a.start_ms <= a.end_ms <= b.start_ms
            assert scaled[-1].end_ms <= native.duration_ms
