"""``GET`` / ``HEAD /audio/{segment_id}?voice=&speed=`` (SYN-1, SYN-3, SYN-5, SYN-6; D5).

GET: 200 with the encoded audio, ``Content-Type`` = the cached file's media type,
``X-Timestamps`` (JSON list of {word, start_ms, end_ms, char_start, char_end}, offsets into
Segment.text) and ``X-Duration-Ms``; a cache miss blocks until synthesized. 404 unknown
segment; 422 bad speed (0.5 <= speed <= 3.0 and speed*20 integral, i.e. 0.05 steps) or unknown voice; 502
JSON {segment_id, reason} when synthesis fails.

HEAD: 200 if a ready cache entry exists, 404 otherwise; never synthesizes.
"""

from __future__ import annotations

import asyncio
import dataclasses
import json

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import JSONResponse

from yomikoe.synthesis.cache import AudioEntry, speed_key
from yomikoe.synthesis.service import SegmentNotFound, SegmentSynthesisFailed, SynthesisService

router = APIRouter()

MIN_SPEED = 0.5
MAX_SPEED = 3.0


def validate(request: Request, voice: str, speed: float) -> float:
    """422 unless 0.5 <= speed <= 3.0 in 0.05 steps and ``voice`` belongs to the backend."""
    steps = speed * 20  # number of 0.05 steps
    if not (MIN_SPEED <= speed <= MAX_SPEED) or abs(steps - round(steps)) > 1e-6:
        raise HTTPException(422, f"speed must be {MIN_SPEED}..{MAX_SPEED} in 0.05 steps")
    if voice not in {v.id for v in request.app.state.tts_backend.voices()}:
        raise HTTPException(422, f"unknown voice {voice!r}")
    return speed_key(speed)


def audio_headers(entry: AudioEntry) -> dict[str, str]:
    return {
        "X-Timestamps": json.dumps([dataclasses.asdict(t) for t in entry.timestamps]),
        "X-Duration-Ms": str(entry.duration_ms),
    }


@router.get("/audio/{segment_id}")
async def get_audio(segment_id: int, voice: str, speed: float, request: Request) -> Response:
    speed = validate(request, voice, speed)
    service: SynthesisService = request.app.state.synthesis
    try:
        entry = await service.get_audio(segment_id, voice, speed)
    except SegmentNotFound:
        raise HTTPException(404, f"segment {segment_id} not found") from None
    except SegmentSynthesisFailed as exc:
        return JSONResponse({"segment_id": exc.segment_id, "reason": exc.reason}, status_code=502)
    assert entry.path is not None
    body = await asyncio.to_thread(entry.path.read_bytes)
    return Response(body, media_type=entry.media_type, headers=audio_headers(entry))


@router.head("/audio/{segment_id}")
async def head_audio(segment_id: int, voice: str, speed: float, request: Request) -> Response:
    speed = validate(request, voice, speed)
    service: SynthesisService = request.app.state.synthesis
    entry = await service.cached(segment_id, voice, speed)
    if entry is None:
        return Response(status_code=404)
    return Response(status_code=200, media_type=entry.media_type, headers=audio_headers(entry))
