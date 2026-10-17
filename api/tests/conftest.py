"""Helpers to build synthetic pages for the ingestion stage tests (ING-2..ING-6).

Import them directly: ``from tests.conftest import make_block, make_page, make_span``.
"""

from __future__ import annotations

import dataclasses
import functools
import os
import threading
import time
from collections.abc import Sequence
from pathlib import Path

import pytest

from hearnarro.ingestion.models import BBox, Block, BlockType, Line, Page, Segment, Span
from hearnarro.synthesis.backend import SynthResult, Voice
from hearnarro.synthesis.cache import AudioEntry
from hearnarro.synthesis.fake import FakeBackend


def union(boxes: Sequence[BBox]) -> BBox:
    return BBox(
        min(b.x0 for b in boxes),
        min(b.y0 for b in boxes),
        max(b.x1 for b in boxes),
        max(b.y1 for b in boxes),
    )


def make_span(
    text: str,
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    size: float = 10.0,
    font: str = "Helvetica",
    bold: bool = False,
    superscript: bool = False,
) -> Span:
    return Span(
        text=text,
        bbox=BBox(x0, y0, x1, y1),
        font=font,
        size=size,
        bold=bold,
        superscript=superscript,
    )


def make_block(
    page: int,
    index: int,
    lines: Sequence[Sequence[Span]] | Sequence[str],
    *,
    x0: float = 72.0,
    y0: float = 72.0,
    width: float = 468.0,
    size: float = 10.0,
    font: str = "Helvetica",
    bold: bool = False,
    type: BlockType = "body",
) -> Block:
    """Build a Block. String lines become one span each, stacked from (x0, y0), each
    ``width`` wide and ``1.2 * size`` tall; span lines keep their own boxes. Bboxes of
    lines and the block are the union of their spans."""
    built: list[Line] = []
    for i, line in enumerate(lines):
        if isinstance(line, str):
            top = y0 + i * 1.2 * size
            spans = [make_span(line, x0, top, x0 + width, top + 1.2 * size, size, font, bold)]
        else:
            spans = list(line)
        built.append(Line(spans=spans, bbox=union([s.bbox for s in spans])))
    return Block(
        page=page,
        index=index,
        bbox=union([ln.bbox for ln in built]),
        lines=built,
        type=type,
    )


def make_page(
    number: int,
    blocks: list[Block],
    width: float = 612.0,
    height: float = 792.0,
    image_bboxes: Sequence[BBox] = (),
    table_bboxes: Sequence[BBox] = (),
    has_text_layer: bool = True,
    figure_bboxes: Sequence[BBox] = (),
) -> Page:
    return Page(
        number=number,
        width=width,
        height=height,
        blocks=blocks,
        image_bboxes=list(image_bboxes),
        table_bboxes=list(table_bboxes),
        has_text_layer=has_text_layer,
        figure_bboxes=list(figure_bboxes),
    )


# ---------------------------------------------------------------------------------------
# M2 synthesis helpers (SYN-1..SYN-6). Test doubles for the SynthesisService's collaborators:
# a spying FakeBackend, an in-memory AudioCache and an in-memory SegmentRepo, plus the 50
# fixture sentences the timestamp invariants run over (ingested, not hand-written).
# Import them directly: ``from tests.conftest import SpyBackend, ...``.
# ---------------------------------------------------------------------------------------

PDF_FIXTURES = Path(__file__).parent / "fixtures" / "pdfs"
SYNTH_FIXTURE_STEMS = ("report_01_zero_trust", "academic_01_seahelm_audio")


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers", "model: needs a real TTS model; skipped unless HEARNARRO_TEST_MODEL=1"
    )
    config.addinivalue_line(
        "markers", "soak: 300-page soak gate (M4); skipped unless HEARNARRO_TEST_SOAK=1"
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Skip every ``@pytest.mark.model`` test unless ``HEARNARRO_TEST_MODEL=1`` and every
    ``@pytest.mark.soak`` test unless ``HEARNARRO_TEST_SOAK=1``."""
    for marker, env in (("model", "HEARNARRO_TEST_MODEL"), ("soak", "HEARNARRO_TEST_SOAK")):
        if os.environ.get(env) == "1":
            continue
        skip = pytest.mark.skip(reason=f"{marker} test: set {env}=1")
        for item in items:
            if marker in item.keywords:
                item.add_marker(skip)


class SpyBackend:
    """FakeBackend that records every call; optional per-call delay and per-text failure."""

    def __init__(self, delay_s: float = 0.0, fail_texts: set[str] | None = None) -> None:
        self.inner = FakeBackend()
        self.name = self.inner.name
        self.delay_s = delay_s
        self.fail_texts = fail_texts or set()
        self.calls: list[tuple[str, str, float, str]] = []  # text, voice, speed, thread
        self._lock = threading.Lock()

    def voices(self) -> list[Voice]:
        return self.inner.voices()

    def speed_range(self) -> tuple[float, float]:
        return self.inner.speed_range()

    def synthesize(self, text: str, voice_id: str, speed: float) -> SynthResult:
        with self._lock:
            self.calls.append((text, voice_id, speed, threading.current_thread().name))
        if self.delay_s:
            time.sleep(self.delay_s)
        if text in self.fail_texts or "*" in self.fail_texts:
            raise RuntimeError("spy backend: induced failure")
        return self.inner.synthesize(text, voice_id, speed)

    @property
    def texts(self) -> list[str]:
        with self._lock:
            return [c[0] for c in self.calls]


class InMemoryCache:
    """Duck-typed AudioCache: same methods, entries in a dict, bytes kept alongside."""

    def __init__(self) -> None:
        self.entries: dict[tuple[int, str, float, str], AudioEntry] = {}
        self.audio: dict[tuple[int, str, float, str], bytes] = {}
        self.failures: dict[tuple[int, str, float, str], str] = {}

    @staticmethod
    def key(segment_id: int, voice_id: str, speed: float, backend: str):
        return (segment_id, voice_id, round(speed, 1), backend)

    async def get(self, segment_id: int, voice_id: str, speed: float, backend: str):
        return self.entries.get(self.key(segment_id, voice_id, speed, backend))

    async def put(self, entry: AudioEntry, audio_bytes: bytes) -> AudioEntry:
        k = self.key(entry.segment_id, entry.voice_id, entry.speed, entry.backend)
        stored = dataclasses.replace(
            entry, status="ready", path=Path(f"mem/{entry.segment_id}/{k[1]}_{k[2]:.1f}")
        )
        self.entries[k] = stored
        self.audio[k] = audio_bytes
        return stored

    async def mark_failed(
        self, segment_id: int, voice_id: str, speed: float, backend: str, reason: str
    ) -> None:
        k = self.key(segment_id, voice_id, speed, backend)
        self.failures[k] = reason
        self.entries[k] = AudioEntry(
            segment_id, voice_id, speed, backend, "failed", None, "", 0, []
        )

    def ready_ids(self) -> set[int]:
        return {k[0] for k, e in self.entries.items() if e.status == "ready"}


class MemorySegmentRepo:
    """Duck-typed SegmentRepo over a list of Segments."""

    def __init__(self, segments: list[Segment]) -> None:
        self.by_id = {s.id: s for s in segments}

    async def get_segment(self, segment_id: int) -> Segment | None:
        return self.by_id.get(segment_id)

    async def segments_from(self, document_id: int, from_order: int, limit: int) -> list[Segment]:
        rows = sorted(
            (
                s
                for s in self.by_id.values()
                if s.document_id == document_id and s.order >= from_order
            ),
            key=lambda s: s.order,
        )
        return rows[:limit]


@functools.cache
def synth_fixture_segments() -> tuple[Segment, ...]:
    """All segments of report_01 (document 1) and academic_01 (document 2), via ``ingest()``.
    Ids are ``document_id * 10_000 + order`` so they are unique and contiguous per document."""
    from hearnarro.ingestion.pipeline import ingest

    out: list[Segment] = []
    for doc_id, stem in enumerate(SYNTH_FIXTURE_STEMS, start=1):
        for seg in ingest(PDF_FIXTURES / f"{stem}.pdf", document_id=doc_id).segments:
            out.append(dataclasses.replace(seg, id=doc_id * 10_000 + seg.order, document_id=doc_id))
    return tuple(out)


def fifty_fixture_sentences() -> list[Segment]:
    """25 segments with at least one word from each fixture, in reading order (SYN-1)."""
    picked: list[Segment] = []
    for doc_id in (1, 2):
        segs = [s for s in synth_fixture_segments() if s.document_id == doc_id]
        picked += [s for s in segs if s.normalized_text.split()][:25]
    assert len(picked) == 50
    return picked


def make_service(
    backend: object | None = None,
    *,
    lookahead: int = 0,
    segments: list[Segment] | None = None,
    cache: InMemoryCache | None = None,
):
    """SynthesisService over the fixture segments, an InMemoryCache and WavEncoder.
    Returns (service, backend, cache). The caller awaits ``service.shutdown()``."""
    from hearnarro.synthesis.encode import WavEncoder
    from hearnarro.synthesis.service import SynthesisService

    backend = backend if backend is not None else SpyBackend()
    cache = cache if cache is not None else InMemoryCache()
    repo = MemorySegmentRepo(list(segments if segments is not None else synth_fixture_segments()))
    service = SynthesisService(backend, WavEncoder(), cache, repo, lookahead=lookahead)  # type: ignore[arg-type]
    return service, backend, cache
