"""Global reader settings (LIB-3): ``GET``/``PUT /settings`` over the key/value table."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from hearnarro.routes.documents import SPEED_MAX, SPEED_MIN, Conn
from hearnarro.storage import repo

router = APIRouter()

DEFAULT_SPEED = 1.25  # user decision, M3 spec section 6
KEY_VOICE = "default_voice_id"
KEY_SPEED = "default_speed"


class GlobalSettings(BaseModel):
    default_voice_id: str | None = None
    default_speed: float = Field(default=DEFAULT_SPEED, ge=SPEED_MIN, le=SPEED_MAX)


async def _read(conn: Conn) -> dict[str, Any]:
    stored = await repo.get_settings(conn)
    speed = stored.get(KEY_SPEED)
    return {
        "default_voice_id": stored.get(KEY_VOICE),
        "default_speed": float(speed) if speed is not None else DEFAULT_SPEED,
    }


@router.get("/settings")
async def get_settings(conn: Conn) -> dict[str, Any]:
    return await _read(conn)


@router.put("/settings")
async def put_settings(body: GlobalSettings, conn: Conn) -> dict[str, Any]:
    """Replace both values; ``default_speed`` must be in [0.5, 3.0] (422 otherwise)."""
    await repo.put_settings(
        conn, {KEY_VOICE: body.default_voice_id, KEY_SPEED: repr(body.default_speed)}
    )
    return await _read(conn)
