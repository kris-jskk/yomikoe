"""D21: FastAPI serves the built web app (``web/dist``) at ``/`` after the API routers.

Contract: ``_agent/specs/m4-library-interfaces.md`` section 1, "Static web (D21)". The dist
path comes from ``HEARNARRO_WEB_DIST``; with a temp dist dir ``/`` serves ``index.html`` and
``/documents`` is still the JSON API; with no dist dir ``/`` is 404 and the API still serves.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from hearnarro.synthesis.encode import WavEncoder
from tests.conftest import SpyBackend
from tests.test_api_documents import client_for

INDEX = "<!doctype html><html><head><title>HearNarro</title></head><body>app</body></html>"


async def test_d21_dist_dir_served_at_root_api_routes_still_win(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text(INDEX)
    (dist / "assets" / "app.js").write_text("console.log('hn');")
    monkeypatch.setenv("HEARNARRO_WEB_DIST", str(dist))
    async with client_for(
        tmp_path / "data", tts_backend=SpyBackend(), encoder=WavEncoder()
    ) as client:
        root = await client.get("/")
        assert root.status_code == 200, root.text
        assert root.headers["content-type"].startswith("text/html")
        assert "<title>HearNarro</title>" in root.text
        asset = await client.get("/assets/app.js")
        assert asset.status_code == 200
        assert "console.log" in asset.text

        docs = await client.get("/documents")
        assert docs.status_code == 200
        assert docs.headers["content-type"].startswith("application/json")
        assert docs.json() == []
        assert (
            (await client.get("/settings")).headers["content-type"].startswith("application/json")
        )
        voices = await client.get("/voices")
        assert voices.status_code == 200
        assert voices.headers["content-type"].startswith("application/json")


async def test_d21_without_dist_dir_root_is_404_and_api_serves(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HEARNARRO_WEB_DIST", str(tmp_path / "no-such-dist"))
    async with client_for(
        tmp_path / "data", tts_backend=SpyBackend(), encoder=WavEncoder()
    ) as client:
        assert (await client.get("/")).status_code == 404
        docs = await client.get("/documents")
        assert docs.status_code == 200
        assert docs.json() == []
