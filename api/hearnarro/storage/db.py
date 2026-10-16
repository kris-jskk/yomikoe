"""SQLite location, engines, migrations and the char_map codec (D7, D9).

Files under the data dir (D7)::

    $HEARNARRO_DATA_DIR/hearnarro.db
    $HEARNARRO_DATA_DIR/pdfs/{sha256}.pdf
"""

from __future__ import annotations

import os
import sqlite3
import sys
from array import array
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import aiosqlite

DATA_DIR_ENV = "HEARNARRO_DATA_DIR"
DEFAULT_DATA_DIR = Path("./data")
DB_FILENAME = "hearnarro.db"
MIGRATIONS_DIR = Path(__file__).parent / "migrations"
BUSY_TIMEOUT_MS = 10_000


def resolve_data_dir(data_dir: Path | str | None) -> Path:
    """Explicit argument, else ``$HEARNARRO_DATA_DIR``, else ``./data``."""
    if data_dir is not None:
        return Path(data_dir)
    env = os.environ.get(DATA_DIR_ENV)
    return Path(env) if env else DEFAULT_DATA_DIR


def db_path(data_dir: Path) -> Path:
    return data_dir / DB_FILENAME


def pdf_dir(data_dir: Path) -> Path:
    return data_dir / "pdfs"


def sync_url(path: Path) -> str:
    return f"sqlite:///{path}"


PRAGMAS = (
    "PRAGMA journal_mode=WAL",
    "PRAGMA foreign_keys=ON",
    f"PRAGMA busy_timeout={BUSY_TIMEOUT_MS}",
)


def _apply_pragmas(conn: Any) -> None:
    for pragma in PRAGMAS:
        conn.execute(pragma)


class Engine:
    """aiosqlite connection factory for the API (D9).

    Every request opens and closes its own connection ("one connection per request"); WAL
    lets the ingestion process write while the API reads. aiosqlite is used directly, not
    through SQLAlchemy's async layer, because that layer requires greenlet (MIT AND
    PSF-2.0), which is outside the Apache/MIT/BSD licence rule.
    """

    def __init__(self, path: Path) -> None:
        self.path = path

    @asynccontextmanager
    async def connect(self) -> AsyncIterator[aiosqlite.Connection]:
        conn = await aiosqlite.connect(self.path, timeout=BUSY_TIMEOUT_MS / 1000)
        try:
            conn.row_factory = aiosqlite.Row
            for pragma in PRAGMAS:
                await conn.execute(pragma)
            yield conn
        finally:
            await conn.close()


def engine(data_dir: Path) -> Engine:
    """Connection factory on ``data_dir/hearnarro.db`` (WAL, foreign keys, busy timeout)."""
    return Engine(db_path(data_dir))


def connect_sync(path: Path | str) -> sqlite3.Connection:
    """Blocking connection for the ingestion worker process (same pragmas as the engine)."""
    conn = sqlite3.connect(str(path), timeout=BUSY_TIMEOUT_MS / 1000)
    _apply_pragmas(conn)
    return conn


def run_migrations(data_dir: Path) -> None:
    """``alembic upgrade head`` against ``data_dir/hearnarro.db``; creates the dir if needed."""
    from alembic import command
    from alembic.config import Config

    data_dir.mkdir(parents=True, exist_ok=True)
    cfg = Config()
    cfg.set_main_option("script_location", str(MIGRATIONS_DIR))
    cfg.set_main_option("sqlalchemy.url", sync_url(db_path(data_dir)).replace("%", "%%"))
    command.upgrade(cfg, "head")
    with connect_sync(db_path(data_dir)):  # journal_mode=WAL is persistent on the file
        pass


def pack_char_map(char_map: list[int]) -> bytes:
    """Packed uint16, little-endian (D7 ``char_map BLOB -- packed uint16 array``)."""
    arr = array("H", char_map)  # raises OverflowError for values > 65535
    if sys.byteorder == "big":
        arr.byteswap()
    return arr.tobytes()


def unpack_char_map(blob: bytes) -> list[int]:
    arr = array("H")
    arr.frombytes(blob)
    if sys.byteorder == "big":
        arr.byteswap()
    return arr.tolist()
