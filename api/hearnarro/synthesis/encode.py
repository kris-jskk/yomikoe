"""Containers for the browser (D7): PCM16 mono in, encoded bytes out.

``WavEncoder`` is stdlib-only, always available and the M2 default (D16). ``OpusEncoder``
(Ogg Opus via ``opuscodec``, D16) is opt-in with ``HEARNARRO_AUDIO_FORMAT=opus``; until it is
implemented it reports itself unavailable and ``default_encoder("opus")`` falls back to WAV
with a warning.
"""

from __future__ import annotations

import io
import logging
import wave
from typing import Protocol

log = logging.getLogger(__name__)


class EncoderUnavailable(RuntimeError):
    """The encoder's dependency (e.g. ffmpeg) is missing on this machine."""


class AudioEncoder(Protocol):
    media_type: str
    ext: str

    def encode(self, pcm: bytes, sample_rate: int) -> bytes: ...


class WavEncoder:
    media_type = "audio/wav"
    ext = "wav"

    def encode(self, pcm: bytes, sample_rate: int) -> bytes:
        if len(pcm) % 2:
            raise ValueError("PCM16 buffer has an odd number of bytes")
        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(sample_rate)
            w.writeframes(pcm)
        return buf.getvalue()


class OpusEncoder:
    """Ogg Opus via ``opuscodec`` (D16). Stub: always unavailable for now."""

    media_type = "audio/ogg"
    ext = "ogg"

    def __init__(self) -> None:
        raise EncoderUnavailable("OpusEncoder is not implemented yet (M2)")

    def encode(self, pcm: bytes, sample_rate: int) -> bytes:
        raise NotImplementedError


_logged = False


def default_encoder(audio_format: str = "wav") -> AudioEncoder:
    """WAV unless ``audio_format == "opus"`` (D16); an unavailable Opus falls back to WAV.
    The choice is logged once per process."""
    global _logged
    encoder: AudioEncoder = WavEncoder()
    reason = "default"
    if audio_format == "opus":
        try:
            encoder = OpusEncoder()
            reason = "requested"
        except EncoderUnavailable as exc:
            reason = f"opus requested but unavailable: {exc}"
            log.warning("audio encoder: %s; using WAV", reason)
    if not _logged:
        log.info("audio encoder: %s (%s)", type(encoder).__name__, reason)
        _logged = True
    return encoder
