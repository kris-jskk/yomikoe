"""SynthesisService: cache, lookahead queue and the single synthesis thread (SYN-1, SYN-3,
SYN-5, SYN-6; D6, D9).

``repo`` is a ``SegmentRepo``: the service reads segments through it (text,
normalized_text, char_map, document_id, order) and never imports a model.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Protocol

from hearnarro.ingestion.models import Segment
from hearnarro.storage.db import Engine
from hearnarro.synthesis.backend import TTSBackend
from hearnarro.synthesis.cache import AudioCache, AudioEntry
from hearnarro.synthesis.encode import AudioEncoder

DEFAULT_LOOKAHEAD = 5
QUEUE_BOUND = 16  # D9 backpressure
SHUTDOWN_WAIT_S = 5.0


class SegmentSynthesisFailed(Exception):
    """The backend raised for one segment; its cache row is marked failed."""

    def __init__(self, segment_id: int, reason: str) -> None:
        super().__init__(f"segment {segment_id}: {reason}")
        self.segment_id = segment_id
        self.reason = reason


class SegmentRepo(Protocol):
    async def get_segment(self, segment_id: int) -> Segment | None: ...

    async def segments_from(
        self, document_id: int, from_order: int, limit: int
    ) -> list[Segment]: ...


class DbSegmentRepo:
    """``SegmentRepo`` over the SQLite ``segments`` table (char_map unpacked)."""

    def __init__(self, db: Engine) -> None:
        self.db = db

    async def get_segment(self, segment_id: int) -> Segment | None:
        raise NotImplementedError

    async def segments_from(self, document_id: int, from_order: int, limit: int) -> list[Segment]:
        raise NotImplementedError


class SynthesisService:
    def __init__(
        self,
        backend: TTSBackend,
        encoder: AudioEncoder,
        cache: AudioCache,
        repo: SegmentRepo,
        *,
        lookahead: int = DEFAULT_LOOKAHEAD,
        executor: ThreadPoolExecutor | None = None,
    ) -> None:
        self.backend = backend
        self.encoder = encoder
        self.cache = cache
        self.repo = repo
        self.lookahead = lookahead
        self._executor = executor

    async def get_audio(self, segment_id: int, voice_id: str, speed: float) -> AudioEntry:
        raise NotImplementedError

    async def prefetch(
        self, document_id: int, from_order: int, voice_id: str, speed: float
    ) -> None:
        raise NotImplementedError

    def queue_depth(self, document_id: int) -> int:
        raise NotImplementedError

    async def shutdown(self) -> None:
        # Stub: nothing is queued or in flight until get_audio/prefetch exist. The app's
        # lifespan calls this on every shutdown, so it must not raise.
        return None
