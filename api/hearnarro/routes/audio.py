"""``GET`` / ``HEAD /audio/{segment_id}?voice=&speed=`` (SYN-1, SYN-3, SYN-5, SYN-6; D5).

GET: 200 with the encoded audio, ``Content-Type`` = encoder media type, ``X-Timestamps``
(JSON list of {word, start_ms, end_ms, char_start, char_end}, offsets into Segment.text) and
``X-Duration-Ms``; a cache miss blocks until synthesized. 404 unknown segment; 422 bad
speed (0.5 <= speed <= 3.0 and speed*10 integral) or unknown voice; 502 JSON
{segment_id, reason} when synthesis fails.

HEAD: 200 if a ready cache entry exists, 404 otherwise; never synthesizes.
"""

from __future__ import annotations

from fastapi import APIRouter, Request, Response

router = APIRouter()

MIN_SPEED = 0.5
MAX_SPEED = 3.0


@router.get("/audio/{segment_id}")
async def get_audio(segment_id: int, voice: str, speed: float, request: Request) -> Response:
    raise NotImplementedError


@router.head("/audio/{segment_id}")
async def head_audio(segment_id: int, voice: str, speed: float, request: Request) -> Response:
    raise NotImplementedError
