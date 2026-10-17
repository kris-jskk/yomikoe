"""FastAPI application factory (D7 storage, D9 process model; M2 synthesis wiring)."""

from __future__ import annotations

import asyncio
import logging
import multiprocessing
from collections.abc import AsyncIterator, Callable
from concurrent.futures import Executor, ProcessPoolExecutor, ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from hearnarro.routes import audio, documents, voices
from hearnarro.routes import settings as settings_routes
from hearnarro.settings import Settings, load_settings, web_dist_dir
from hearnarro.storage.db import engine, pdf_dir, resolve_data_dir, run_migrations
from hearnarro.synthesis.backend import TTSBackend
from hearnarro.synthesis.cache import AudioCache
from hearnarro.synthesis.encode import AudioEncoder, default_encoder
from hearnarro.synthesis.fake import FakeBackend
from hearnarro.synthesis.service import DbSegmentRepo, SynthesisService

log = logging.getLogger(__name__)

MAX_UPLOAD_BYTES = 100 * 1024 * 1024  # ING-1: PDFs up to 100 MB
INGEST_WORKERS = 2  # D9


def _default_executor() -> Executor:
    """D9 pool with the spawn start method, never fork (Linux's default). A worker forked
    while the API holds a SQLite connection inherits SQLite's per-inode lock bookkeeping
    without the POSIX locks behind it; its writes then fail with "disk I/O error" or corrupt
    the file (found in the Docker image, D30)."""
    return ProcessPoolExecutor(
        max_workers=INGEST_WORKERS, mp_context=multiprocessing.get_context("spawn")
    )


def build_backend(settings: Settings) -> TTSBackend:
    """The configured TTSBackend. Kokoro is imported lazily: only its module names a model."""
    if settings.tts_backend == "kokoro":
        from hearnarro.synthesis.kokoro_backend import KokoroBackend

        assert settings.kokoro_revision is not None  # load_settings enforces it
        return KokoroBackend(revision=settings.kokoro_revision)
    return FakeBackend()


def create_app(
    data_dir: Path | None = None,
    *,
    max_upload_bytes: int = MAX_UPLOAD_BYTES,
    executor_factory: Callable[[], Executor] | None = None,
    tts_backend: TTSBackend | None = None,
    encoder: AudioEncoder | None = None,
    lookahead: int | None = None,
) -> FastAPI:
    """Build the app. ``data_dir`` defaults to ``$HEARNARRO_DATA_DIR`` or ``./data``.

    ``executor_factory`` exists for tests that must monkeypatch the ingestion function (a
    patch does not cross into a spawned process); production always uses the process pool.
    ``tts_backend``, ``encoder`` and ``lookahead`` override the settings (tests inject
    FakeBackend variants and WavEncoder); unset, they come from ``load_settings()``.
    """
    root = resolve_data_dir(data_dir).resolve()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        pdf_dir(root).mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(run_migrations, root)
        app.state.engine = engine(root)
        app.state.ingest_executor = (executor_factory or _default_executor)()
        app.state.ingest_tasks = set()
        app.state.ingest_seconds = {}
        # D9: one synthesis thread; the backend (model load) is built on it, off the loop.
        app.state.synth_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="synth")
        backend, n_ahead, enc = tts_backend, lookahead, encoder
        if backend is None or n_ahead is None or enc is None:
            settings = load_settings()
            if backend is None:
                loop = asyncio.get_running_loop()
                backend = await loop.run_in_executor(
                    app.state.synth_executor, build_backend, settings
                )
            n_ahead = n_ahead if n_ahead is not None else settings.lookahead
            enc = enc if enc is not None else default_encoder(settings.audio_format)
        log.info("TTS backend: %s; lookahead %s; encoder %s", backend.name, n_ahead, enc.ext)
        app.state.tts_backend = backend
        app.state.encoder = enc
        app.state.audio_cache = AudioCache(root, app.state.engine)
        app.state.synthesis = SynthesisService(
            backend,
            app.state.encoder,
            app.state.audio_cache,
            DbSegmentRepo(app.state.engine),
            lookahead=n_ahead,
            executor=app.state.synth_executor,
        )
        try:
            yield
        finally:
            await app.state.synthesis.shutdown()  # waits <= 5 s for the job in flight
            app.state.synth_executor.shutdown(wait=False, cancel_futures=True)
            executor: Executor = app.state.ingest_executor
            await asyncio.to_thread(executor.shutdown, wait=True, cancel_futures=True)
            tasks = list(app.state.ingest_tasks)
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

    app = FastAPI(title="HearNarro", version="0.1.0", lifespan=lifespan)
    app.state.data_dir = root
    app.state.max_upload_bytes = max_upload_bytes
    app.include_router(documents.router)
    app.include_router(audio.router)
    app.include_router(voices.router)
    app.include_router(settings_routes.router)
    dist = web_dist_dir()
    if dist is not None:  # D21: after the routers, so the API paths keep winning
        app.mount("/", StaticFiles(directory=dist, html=True), name="web")
    return app
