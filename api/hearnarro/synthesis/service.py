"""SynthesisService: cache, lookahead queue and the single synthesis thread (SYN-1, SYN-3,
SYN-5, SYN-6; D6, D9, D17).

``repo`` is a ``SegmentRepo``: the service reads segments through it (text,
normalized_text, char_map, document_id, order) and never imports a model.

Flow of ``get_audio(k)``: a ready cache entry returns at once; a miss runs on the synthesis
executor ahead of any queued lookahead job (the lookahead worker hands the executor one job
at a time, so an explicit request waits for at most the job in flight). Either way the
window ``order(k)+1 .. order(k)+N`` of the same document, voice and speed is then enqueued,
skipping entries already cached, queued or in flight; it stops at the document end. A
request whose order is outside ``[last, last + N]`` for that (document, voice, speed), or
that changes voice or speed, is a seek: the document's queue is cleared first.
"""

from __future__ import annotations

import asyncio
import collections
import contextlib
import dataclasses
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Protocol

from hearnarro.ingestion.models import Segment
from hearnarro.storage import repo as db_repo
from hearnarro.storage.db import Engine, unpack_char_map
from hearnarro.synthesis.backend import TTSBackend, WordTimestamp
from hearnarro.synthesis.cache import AudioCache, AudioEntry, speed_key
from hearnarro.synthesis.encode import AudioEncoder
from hearnarro.synthesis.stretch import scale_timestamps, stretch_pcm

log = logging.getLogger(__name__)

DEFAULT_LOOKAHEAD = 5
QUEUE_BOUND = 16  # D9 backpressure
SHUTDOWN_WAIT_S = 5.0
MAX_EXPLICIT_FAILURES = 2  # a failed row is retried once on the next explicit GET

Key = tuple[int, str, float]  # segment_id, voice_id, speed_key


class SegmentSynthesisFailed(Exception):
    """The backend raised for one segment; its cache row is marked failed."""

    def __init__(self, segment_id: int, reason: str) -> None:
        super().__init__(f"segment {segment_id}: {reason}")
        self.segment_id = segment_id
        self.reason = reason


class SegmentNotFound(LookupError):
    """No segment with this id."""


class SegmentRepo(Protocol):
    async def get_segment(self, segment_id: int) -> Segment | None: ...

    async def segments_from(
        self, document_id: int, from_order: int, limit: int
    ) -> list[Segment]: ...


def _segment(row: dict) -> Segment:
    return Segment(
        id=row["id"],
        document_id=row["document_id"],
        block_id=row["block_id"],
        order=row["order"],
        section_id=row["section_id"],
        text=row["text"],
        normalized_text=row["normalized_text"],
        char_start=row["char_start"],
        char_end=row["char_end"],
        char_map=unpack_char_map(row["char_map"]),
    )


class DbSegmentRepo:
    """``SegmentRepo`` over the SQLite ``segments`` table (char_map unpacked)."""

    def __init__(self, db: Engine) -> None:
        self.db = db

    async def get_segment(self, segment_id: int) -> Segment | None:
        async with self.db.connect() as conn:
            row = await db_repo.get_segment_row(conn, segment_id)
        return _segment(row) if row is not None else None

    async def segments_from(self, document_id: int, from_order: int, limit: int) -> list[Segment]:
        async with self.db.connect() as conn:
            rows = await db_repo.segment_rows_from(conn, document_id, from_order, limit)
        return [_segment(r) for r in rows]


def to_text_offsets(ts: list[WordTimestamp], seg: Segment) -> list[WordTimestamp]:
    """Backend offsets (into ``normalized_text``) -> ``text`` offsets through ``char_map``:
    ``char_start = char_map[ns]``, ``char_end = char_map[ne - 1] + 1`` (SYN-1)."""
    cmap = seg.char_map
    if not cmap:
        return list(ts)
    last = len(cmap) - 1
    out: list[WordTimestamp] = []
    for t in ts:
        ns = min(max(t.char_start, 0), last)
        ne = min(max(t.char_end, ns + 1), last + 1)
        start = cmap[ns]
        end = max(cmap[ne - 1] + 1, start + 1)
        out.append(dataclasses.replace(t, char_start=start, char_end=min(end, len(seg.text))))
    return out


def _clamp(ts: list[WordTimestamp], duration_ms: int) -> list[WordTimestamp]:
    out = []
    for t in ts:
        end = min(t.end_ms, duration_ms)
        out.append(dataclasses.replace(t, start_ms=min(t.start_ms, end), end_ms=end))
    return out


@dataclasses.dataclass(frozen=True)
class _Job:
    segment: Segment
    voice_id: str
    speed: float

    @property
    def key(self) -> Key:
        return (self.segment.id, self.voice_id, self.speed)


@dataclasses.dataclass
class _Rendered:
    speed: float
    pcm: bytes
    sample_rate: int
    timestamps: list[WordTimestamp]


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
        self._owns_executor = executor is None
        self._executor = executor or ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="synth"
        )  # D9: one synthesis thread
        self._queue: collections.deque[_Job] = collections.deque()
        self._inflight: dict[Key, asyncio.Future[AudioEntry]] = {}
        self._last: dict[int, tuple[str, float, int]] = {}  # document -> voice, speed, order
        self._wake: asyncio.Event | None = None
        self._worker: asyncio.Task[None] | None = None
        self._closed = False

    # --- public API ---------------------------------------------------------------------

    async def get_audio(self, segment_id: int, voice_id: str, speed: float) -> AudioEntry:
        speed = speed_key(speed)
        seg = await self.repo.get_segment(segment_id)
        if seg is None:
            raise SegmentNotFound(segment_id)
        self._note_request(seg, voice_id, speed)
        try:
            entry = await self.cache.get(seg.id, voice_id, speed, self.backend.name)
            if entry is not None and entry.status == "ready":
                return entry
            if entry is not None and entry.failures >= MAX_EXPLICIT_FAILURES:
                raise SegmentSynthesisFailed(seg.id, f"failed {entry.failures} times; not retried")
            self._drop_queued({(seg.id, voice_id, speed)})
            return await self._produce(seg, voice_id, speed)
        finally:
            await self._enqueue_window(seg.document_id, seg.order + 1, voice_id, speed)

    async def cached(self, segment_id: int, voice_id: str, speed: float) -> AudioEntry | None:
        """The ready cache entry, or None; never synthesizes (HEAD)."""
        entry = await self.cache.get(segment_id, voice_id, speed_key(speed), self.backend.name)
        return entry if entry is not None and entry.status == "ready" else None

    async def prefetch(
        self, document_id: int, from_order: int, voice_id: str, speed: float
    ) -> None:
        """Explicit seek: clear the document's queue, enqueue ``from_order`` onward
        (``lookahead`` segments, at least one)."""
        speed = speed_key(speed)
        dropped = self._clear_document(document_id)
        log.info(
            "prefetch: document %s from order %s; queue cleared (%d dropped)",
            document_id,
            from_order,
            dropped,
        )
        self._last[document_id] = (voice_id, speed, from_order)
        await self._enqueue_window(
            document_id, from_order, voice_id, speed, count=max(self.lookahead, 1)
        )

    def queue_depth(self, document_id: int) -> int:
        """Jobs waiting for this document (the one in flight is not counted)."""
        return sum(1 for j in self._queue if j.segment.document_id == document_id)

    async def shutdown(self) -> None:
        """Cancel the queue, wait <= 5 s for the job in flight, then drop the rest."""
        self._closed = True
        self._queue.clear()
        if self._worker is not None:
            self._worker.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await self._worker
            self._worker = None
        loop = asyncio.get_running_loop()
        try:
            await asyncio.wait_for(
                loop.run_in_executor(self._executor, lambda: None), SHUTDOWN_WAIT_S
            )
        except (TimeoutError, RuntimeError):  # RuntimeError: executor already shut down
            log.warning("synthesis shutdown: in-flight job did not finish in %ss", SHUTDOWN_WAIT_S)
        if self._owns_executor:
            self._executor.shutdown(wait=False, cancel_futures=True)

    # --- queue --------------------------------------------------------------------------

    def _note_request(self, seg: Segment, voice_id: str, speed: float) -> None:
        last = self._last.get(seg.document_id)
        self._last[seg.document_id] = (voice_id, speed, seg.order)
        if last is None:
            return
        last_voice, last_speed, last_order = last
        if (last_voice, last_speed) != (voice_id, speed) or not (
            last_order <= seg.order <= last_order + self.lookahead
        ):
            dropped = self._clear_document(seg.document_id)
            log.info(
                "seek: document %s order %s (voice %s, speed %.2f) outside [%s, %s] of "
                "(voice %s, speed %.2f); queue cleared (%d dropped)",
                seg.document_id,
                seg.order,
                voice_id,
                speed,
                last_order,
                last_order + self.lookahead,
                last_voice,
                last_speed,
                dropped,
            )

    def _clear_document(self, document_id: int) -> int:
        before = len(self._queue)
        self._queue = collections.deque(
            j for j in self._queue if j.segment.document_id != document_id
        )
        return before - len(self._queue)

    def _drop_queued(self, keys: set[Key]) -> None:
        self._queue = collections.deque(j for j in self._queue if j.key not in keys)

    async def _enqueue_window(
        self,
        document_id: int,
        from_order: int,
        voice_id: str,
        speed: float,
        count: int | None = None,
    ) -> None:
        n = self.lookahead if count is None else count
        if self._closed or n <= 0:
            return
        queued = {j.key for j in self._queue}
        added = 0
        for seg in await self.repo.segments_from(document_id, from_order, n):
            key = (seg.id, voice_id, speed)
            if key in queued or key in self._inflight:
                continue
            if len(self._queue) >= QUEUE_BOUND:
                break
            if await self.cache.get(seg.id, voice_id, speed, self.backend.name) is not None:
                continue  # ready, or failed (the queue never retries a failed row)
            self._queue.append(_Job(seg, voice_id, speed))
            added += 1
        if added:
            self._ensure_worker()
            assert self._wake is not None
            self._wake.set()

    def _ensure_worker(self) -> None:
        if self._worker is None or self._worker.done():
            self._wake = self._wake or asyncio.Event()
            self._worker = asyncio.get_running_loop().create_task(self._run_queue())

    async def _run_queue(self) -> None:
        assert self._wake is not None
        while not self._closed:
            if not self._queue:
                self._wake.clear()
                await self._wake.wait()
                continue
            job = self._queue.popleft()
            try:
                existing = await self.cache.get(
                    job.segment.id, job.voice_id, job.speed, self.backend.name
                )
                if existing is None:
                    await self._produce(job.segment, job.voice_id, job.speed)
            except SegmentSynthesisFailed:
                pass  # row marked failed; the queue moves on
            except Exception:
                log.exception("lookahead job for segment %s failed", job.segment.id)

    # --- synthesis ----------------------------------------------------------------------

    async def _produce(self, seg: Segment, voice_id: str, speed: float) -> AudioEntry:
        """Synthesize (once per key even if requested twice), cache and return."""
        key = (seg.id, voice_id, speed)
        pending = self._inflight.get(key)
        if pending is not None:
            return await asyncio.shield(pending)
        fut: asyncio.Future[AudioEntry] = asyncio.get_running_loop().create_future()
        self._inflight[key] = fut
        try:
            entry = await self._synthesize_and_store(seg, voice_id, speed)
        except BaseException as exc:
            if isinstance(exc, asyncio.CancelledError):
                fut.cancel()
            else:
                fut.set_exception(exc)
                fut.exception()  # mark retrieved: nobody else may be waiting
            raise
        else:
            fut.set_result(entry)
            return entry
        finally:
            self._inflight.pop(key, None)

    async def _synthesize_and_store(self, seg: Segment, voice_id: str, speed: float) -> AudioEntry:
        loop = asyncio.get_running_loop()
        try:
            rendered = await loop.run_in_executor(
                self._executor, self._render, seg, voice_id, speed
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            reason = f"{type(exc).__name__}: {exc}"
            log.warning("synthesis failed for segment %s: %s", seg.id, reason)
            await self.cache.mark_failed(seg.id, voice_id, speed, self.backend.name, reason)
            raise SegmentSynthesisFailed(seg.id, reason) from exc
        first: AudioEntry | None = None
        for i, (r, audio) in enumerate(rendered):
            if (
                i > 0
                and (await self.cache.get(seg.id, voice_id, r.speed, self.backend.name)) is not None
            ):
                continue  # the native file of a stretched request is cached once
            entry = AudioEntry(
                segment_id=seg.id,
                voice_id=voice_id,
                speed=r.speed,
                backend=self.backend.name,
                status="ready",
                path=None,
                media_type=self.encoder.media_type,
                duration_ms=int((len(r.pcm) // 2) * 1000 / r.sample_rate),
                timestamps=r.timestamps,
                document_id=seg.document_id,
            )
            stored = await self.cache.put(entry, audio)
            first = first or stored
        assert first is not None
        return first

    def _render(self, seg: Segment, voice_id: str, speed: float) -> list[tuple[_Rendered, bytes]]:
        """On the synthesis thread: synthesize (+ stretch above the native max, D6/D17) and
        encode. Returns the requested speed first, then the native-max file if stretched."""
        _, native_max = self.backend.speed_range()
        if speed <= native_max:
            result = self.backend.synthesize(seg.normalized_text, voice_id, speed)
            ts = to_text_offsets(result.timestamps, seg)
            outs = [_Rendered(speed, result.audio, result.sample_rate, ts)]
        else:
            result = self.backend.synthesize(seg.normalized_text, voice_id, native_max)
            native_ts = to_text_offsets(result.timestamps, seg)
            ratio = speed / native_max
            pcm = stretch_pcm(result.audio, result.sample_rate, ratio)
            duration_ms = int((len(pcm) // 2) * 1000 / result.sample_rate)
            ts = _clamp(scale_timestamps(native_ts, ratio), duration_ms)
            outs = [
                _Rendered(speed, pcm, result.sample_rate, ts),
                _Rendered(speed_key(native_max), result.audio, result.sample_rate, native_ts),
            ]
        return [(r, self.encoder.encode(r.pcm, r.sample_rate)) for r in outs]
