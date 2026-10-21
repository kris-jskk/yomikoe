"""PLAY-11: the equation speed factor is a global setting on ``GET``/``PUT /settings``.

Spec ``_agent/specs/m5-academic-reading.md`` section 4d: ``equation_speed_factor`` defaults to
0.8 when unset, is bounded to [0.5, 1.0] (422 outside), persists in the key/value settings
table under key ``equation_speed_factor`` (no migration), and a PUT body without it (the web
client's two-field body) keeps the default.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from tests.conftest import SpyBackend
from tests.test_api_documents import client_for
from yomikoe.storage.db import connect_sync, db_path
from yomikoe.synthesis.encode import WavEncoder

KEY = "equation_speed_factor"


def _kwargs() -> dict[str, Any]:
    return {"tts_backend": SpyBackend(), "encoder": WavEncoder()}


def _stored(data_dir: Path) -> str | None:
    with connect_sync(db_path(data_dir)) as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (KEY,)).fetchone()
    return row[0] if row else None


async def test_play11_equation_speed_factor_defaults_to_0_8(tmp_path: Path) -> None:
    async with client_for(tmp_path, **_kwargs()) as client:
        body = (await client.get("/settings")).json()
    assert body[KEY] == 0.8


async def test_play11_equation_speed_factor_put_persists_in_settings_table(
    tmp_path: Path,
) -> None:
    async with client_for(tmp_path, **_kwargs()) as client:
        put = await client.put(
            "/settings",
            json={"default_voice_id": None, "default_speed": 1.25, KEY: 0.65},
        )
        assert put.status_code == 200, put.text
        assert put.json()[KEY] == 0.65
    assert _stored(tmp_path) is not None and float(_stored(tmp_path) or "nan") == 0.65
    async with client_for(tmp_path, **_kwargs()) as client:  # survives a restart
        assert (await client.get("/settings")).json()[KEY] == 0.65


async def test_play11_two_field_put_keeps_default_factor(tmp_path: Path) -> None:
    async with client_for(tmp_path, **_kwargs()) as client:
        put = await client.put("/settings", json={"default_voice_id": None, "default_speed": 1.5})
        assert put.status_code == 200, put.text
        body = (await client.get("/settings")).json()
    assert body["default_speed"] == 1.5
    assert body[KEY] == 0.8


@pytest.mark.parametrize(
    ("factor", "status"), [(0.49, 422), (1.01, 422), (0.5, 200), (1.0, 200)]
)
async def test_play11_equation_speed_factor_bounds(
    tmp_path: Path, factor: float, status: int
) -> None:
    async with client_for(tmp_path, **_kwargs()) as client:
        resp = await client.put(
            "/settings",
            json={"default_voice_id": None, "default_speed": 1.25, KEY: factor},
        )
        assert resp.status_code == status, resp.text
        expected = factor if status == 200 else 0.8
        assert (await client.get("/settings")).json()[KEY] == expected
