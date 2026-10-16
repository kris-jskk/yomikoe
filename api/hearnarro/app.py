"""FastAPI application factory (M1 skeleton; D7 storage, D9 process model)."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator, Callable
from concurrent.futures import Executor, ProcessPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from hearnarro.routes import documents
from hearnarro.storage.db import engine, pdf_dir, resolve_data_dir, run_migrations

log = logging.getLogger(__name__)

MAX_UPLOAD_BYTES = 100 * 1024 * 1024  # ING-1: PDFs up to 100 MB
INGEST_WORKERS = 2  # D9


def _default_executor() -> Executor:
    return ProcessPoolExecutor(max_workers=INGEST_WORKERS)


def create_app(
    data_dir: Path | None = None,
    *,
    max_upload_bytes: int = MAX_UPLOAD_BYTES,
    executor_factory: Callable[[], Executor] | None = None,
) -> FastAPI:
    """Build the app. ``data_dir`` defaults to ``$HEARNARRO_DATA_DIR`` or ``./data``.

    ``executor_factory`` exists for tests that must monkeypatch the ingestion function (a
    patch does not cross into a spawned process); production always uses the process pool.
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
        try:
            yield
        finally:
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
    return app
