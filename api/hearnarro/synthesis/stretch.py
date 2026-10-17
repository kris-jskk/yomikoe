"""Time-stretch for speeds above the backend's native range (D6, SYN-3).

The service synthesizes at the native maximum and stretches by
``ratio = requested / native_max`` (1.0 < ratio <= 1.5), then scales every timestamp by
``1 / ratio``. The implementation (ffmpeg ``atempo`` or numpy WSOLA) is the M2 survey's
choice; the interface is fixed.
"""

from __future__ import annotations

from hearnarro.synthesis.backend import WordTimestamp

MAX_RATIO = 1.5


def stretch_pcm(pcm: bytes, sample_rate: int, ratio: float) -> bytes:
    """PCM16 mono in, PCM16 mono out, ``len(out) ≈ len(pcm) / ratio``; pitch preserved."""
    raise NotImplementedError


def scale_timestamps(ts: list[WordTimestamp], ratio: float) -> list[WordTimestamp]:
    """start_ms and end_ms times ``1 / ratio`` as ints; order and char offsets unchanged."""
    raise NotImplementedError
