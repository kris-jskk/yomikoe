"""Write-through audio cache (D7, SYN-6).

Files: ``data_dir/audio/{document_id}/{segment_id}/{voice_id}_{speed:.2f}.{ext}``; rows in the
``audio_cache`` table (primary key segment_id, voice_id, speed, backend). ``put`` writes
``path + ".tmp"``, renames, then inserts the row with status ``ready``.

``media_type`` is not a column: it is derived from the file extension at read time. A
``failed`` row keeps ``{"failures": n, "reason": ...}`` in ``timestamps_json`` (no migration);
the service retries it once on the next explicit request (spec amendment, code-map review).
"""

from __future__ import annotations

import asyncio
import dataclasses
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from hearnarro.storage.db import Engine
from hearnarro.storage.repo import now_iso
from hearnarro.synthesis.backend import WordTimestamp

MEDIA_TYPES = {"wav": "audio/wav", "ogg": "audio/ogg", "opus": "audio/ogg", "webm": "audio/webm"}
EXTENSIONS = {"audio/wav": "wav", "audio/ogg": "ogg", "audio/webm": "webm"}


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
    document_id: int = 0  # needed for the file path (code-map review amendment)
    failures: int = 0  # failed rows only: how many explicit attempts have failed


def speed_key(speed: float) -> float:
    """Cache key for a speed: two decimals (the API accepts 0.05 steps, SYN-3). Rows written
    before the 0.05-step change keep their stored one-decimal ``path`` (``..._2.0.wav``) and
    still hit, because ``get`` reads the file from the row, not from ``file_path``."""
    return round(float(speed), 2)


def media_type_for(path: Path) -> str:
    return MEDIA_TYPES.get(path.suffix.lstrip(".").lower(), "application/octet-stream")


def timestamps_to_json(ts: list[WordTimestamp]) -> str:
    return json.dumps([dataclasses.asdict(t) for t in ts])


def timestamps_from_json(raw: str | None) -> list[WordTimestamp]:
    data = json.loads(raw) if raw else []
    return [WordTimestamp(**t) for t in data] if isinstance(data, list) else []


class AudioCache:
    def __init__(self, data_dir: Path, db: Engine) -> None:
        self.data_dir = data_dir
        self.db = db

    def file_path(self, entry: AudioEntry) -> Path:
        ext = EXTENSIONS.get(entry.media_type, "bin")
        name = f"{entry.voice_id}_{speed_key(entry.speed):.2f}.{ext}"
        return self.data_dir / "audio" / str(entry.document_id) / str(entry.segment_id) / name

    async def _row(
        self, segment_id: int, voice_id: str, speed: float, backend: str
    ) -> dict[str, Any] | None:
        async with (
            self.db.connect() as conn,
            conn.execute(
                "SELECT status, path, duration_ms, timestamps_json FROM audio_cache "
                "WHERE segment_id = ? AND voice_id = ? AND speed = ? AND backend = ?",
                (segment_id, voice_id, speed_key(speed), backend),
            ) as cur,
        ):
            row = await cur.fetchone()
        return dict(row) if row is not None else None

    async def get(
        self, segment_id: int, voice_id: str, speed: float, backend: str
    ) -> AudioEntry | None:
        row = await self._row(segment_id, voice_id, speed, backend)
        if row is None:
            return None
        if row["status"] == "failed":
            info = json.loads(row["timestamps_json"] or "{}")
            failures = int(info.get("failures", 1)) if isinstance(info, dict) else 1
            return AudioEntry(
                segment_id,
                voice_id,
                speed_key(speed),
                backend,
                "failed",
                None,
                "",
                0,
                [],
                failures=failures,
            )
        path = self.data_dir / row["path"]
        if not path.is_file():  # file removed under us: treat as a miss
            return None
        document_id = int(path.parent.parent.name) if path.parent.parent.name.isdigit() else 0
        return AudioEntry(
            segment_id=segment_id,
            voice_id=voice_id,
            speed=speed_key(speed),
            backend=backend,
            status="ready",
            path=path,
            media_type=media_type_for(path),
            duration_ms=int(row["duration_ms"] or 0),
            timestamps=timestamps_from_json(row["timestamps_json"]),
            document_id=document_id,
        )

    async def put(self, entry: AudioEntry, audio_bytes: bytes) -> AudioEntry:
        path = self.file_path(entry)

        def write() -> None:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_name(path.name + ".tmp")
            tmp.write_bytes(audio_bytes)
            os.replace(tmp, path)

        await asyncio.to_thread(write)
        async with self.db.connect() as conn:
            await conn.execute(
                "INSERT OR REPLACE INTO audio_cache (segment_id, voice_id, speed, backend, "
                "status, path, duration_ms, timestamps_json, created_at) "
                "VALUES (?, ?, ?, ?, 'ready', ?, ?, ?, ?)",
                (
                    entry.segment_id,
                    entry.voice_id,
                    speed_key(entry.speed),
                    entry.backend,
                    str(path.relative_to(self.data_dir)),
                    entry.duration_ms,
                    timestamps_to_json(entry.timestamps),
                    now_iso(),
                ),
            )
            await conn.commit()
        return dataclasses.replace(
            entry,
            status="ready",
            path=path,
            speed=speed_key(entry.speed),
            media_type=media_type_for(path),
            failures=0,
        )

    async def mark_failed(
        self, segment_id: int, voice_id: str, speed: float, backend: str, reason: str
    ) -> None:
        prior = await self._row(segment_id, voice_id, speed, backend)
        failures = 1
        if prior is not None and prior["status"] == "failed":
            info = json.loads(prior["timestamps_json"] or "{}")
            failures = (int(info.get("failures", 1)) if isinstance(info, dict) else 1) + 1
        async with self.db.connect() as conn:
            await conn.execute(
                "INSERT OR REPLACE INTO audio_cache (segment_id, voice_id, speed, backend, "
                "status, path, duration_ms, timestamps_json, created_at) "
                "VALUES (?, ?, ?, ?, 'failed', NULL, NULL, ?, ?)",
                (
                    segment_id,
                    voice_id,
                    speed_key(speed),
                    backend,
                    json.dumps({"failures": failures, "reason": reason}),
                    now_iso(),
                ),
            )
            await conn.commit()
