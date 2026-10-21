"""Global reader settings (LIB-3, PLAY-11): ``GET``/``PUT /settings`` over the key/value table."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from yomikoe.routes.documents import SPEED_MAX, SPEED_MIN, Conn
from yomikoe.storage import repo

router = APIRouter()

DEFAULT_SPEED = 1.25  # user decision, M3 spec section 6
KEY_VOICE = "default_voice_id"
KEY_SPEED = "default_speed"
# PLAY-11 (spec m5 section 4d): playback-rate factor the web player applies to maths segments.
DEFAULT_EQUATION_SPEED_FACTOR = 0.8
EQUATION_SPEED_FACTOR_MIN, EQUATION_SPEED_FACTOR_MAX = 0.5, 1.0
KEY_EQUATION_SPEED = "equation_speed_factor"


class GlobalSettings(BaseModel):
    default_voice_id: str | None = None
    default_speed: float = Field(default=DEFAULT_SPEED, ge=SPEED_MIN, le=SPEED_MAX)
    equation_speed_factor: float = Field(
        default=DEFAULT_EQUATION_SPEED_FACTOR,
        ge=EQUATION_SPEED_FACTOR_MIN,
        le=EQUATION_SPEED_FACTOR_MAX,
    )


async def _read(conn: Conn) -> dict[str, Any]:
    stored = await repo.get_settings(conn)
    speed = stored.get(KEY_SPEED)
    factor = stored.get(KEY_EQUATION_SPEED)
    return {
        "default_voice_id": stored.get(KEY_VOICE),
        "default_speed": float(speed) if speed is not None else DEFAULT_SPEED,
        "equation_speed_factor": (
            float(factor) if factor is not None else DEFAULT_EQUATION_SPEED_FACTOR
        ),
    }


@router.get("/settings")
async def get_settings(conn: Conn) -> dict[str, Any]:
    return await _read(conn)


@router.put("/settings")
async def put_settings(body: GlobalSettings, conn: Conn) -> dict[str, Any]:
    """Replace the values; ``default_speed`` must be in [0.5, 3.0] and
    ``equation_speed_factor`` in [0.5, 1.0] (422 otherwise). A body without the factor stores
    its default 0.8 (PLAY-11)."""
    await repo.put_settings(
        conn,
        {
            KEY_VOICE: body.default_voice_id,
            KEY_SPEED: repr(body.default_speed),
            KEY_EQUATION_SPEED: repr(body.equation_speed_factor),
        },
    )
    return await _read(conn)
