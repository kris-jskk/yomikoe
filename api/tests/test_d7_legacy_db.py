"""D7: the SQLite file is ``yomikoe.db``; a pre-rename ``hearnarro.db`` is moved on startup."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from yomikoe.storage.db import DB_FILENAME, LEGACY_DB_FILENAME, run_migrations


def _tables(path: Path) -> set[str]:
    with sqlite3.connect(path) as conn:
        return {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def test_d7_legacy_db_filename_is_moved(tmp_path: Path) -> None:
    legacy = tmp_path / LEGACY_DB_FILENAME
    with sqlite3.connect(legacy) as conn:
        conn.execute("CREATE TABLE marker (v TEXT)")
        conn.execute("INSERT INTO marker VALUES ('kept')")
    (tmp_path / f"{LEGACY_DB_FILENAME}-shm").write_bytes(b"")

    run_migrations(tmp_path)

    new = tmp_path / DB_FILENAME
    assert new.exists()
    assert not legacy.exists()
    assert not (tmp_path / f"{LEGACY_DB_FILENAME}-shm").exists()
    with sqlite3.connect(new) as conn:
        assert conn.execute("SELECT v FROM marker").fetchone() == ("kept",)
    assert "documents" in _tables(new)


def test_d7_fresh_data_dir_creates_yomikoe_db(tmp_path: Path) -> None:
    data_dir = tmp_path / "fresh"
    run_migrations(data_dir)
    assert (data_dir / DB_FILENAME).exists()
    assert not (data_dir / LEGACY_DB_FILENAME).exists()
    assert "documents" in _tables(data_dir / DB_FILENAME)
