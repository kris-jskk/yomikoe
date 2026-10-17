"""``GET /voices``: every Voice across registered backends (SYN-2)."""

from __future__ import annotations

import dataclasses
from typing import Any

from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/voices")
async def list_voices(request: Request) -> list[dict[str, Any]]:
    """``[{id, name, backend, language, gender}]`` from ``app.state.tts_backend.voices()``."""
    return [dataclasses.asdict(v) for v in request.app.state.tts_backend.voices()]
