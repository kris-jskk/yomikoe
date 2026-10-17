"""Write-through audio cache (D7, SYN-6).

Files: ``data_dir/audio/{document_id}/{segment_id}/{voice_id}_{speed:.1f}.{ext}``; rows in the
``audio_cache`` table (primary key segment_id, voice_id, speed, backend). ``put`` writes
``path + ".tmp"``, renames, then inserts the row with status ``ready``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from hearnarro.storage.db import Engine
from hearnarro.synthesis.backend import WordTimestamp


@dataclass
class AudioEntry:
    segment_id: int
    voice_id: str
    speed: float
    backend: str
    status: str  # "ready" | "failed"
    path: Path | None
    media_type: str
    duration_ms: int
    timestamps: list[WordTimestamp]  # offsets into Segment.text


class AudioCache:
    def __init__(self, data_dir: Path, db: Engine) -> None:
        self.data_dir = data_dir
        self.db = db

    async def get(
        self, segment_id: int, voice_id: str, speed: float, backend: str
    ) -> AudioEntry | None:
        raise NotImplementedError

    async def put(self, entry: AudioEntry, audio_bytes: bytes) -> AudioEntry:
        raise NotImplementedError

    async def mark_failed(
        self, segment_id: int, voice_id: str, speed: float, backend: str, reason: str
    ) -> None:
        raise NotImplementedError
