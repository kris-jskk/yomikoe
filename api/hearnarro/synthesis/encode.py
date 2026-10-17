"""Containers for the browser (D7): PCM16 mono in, encoded bytes out.

``WavEncoder`` is stdlib-only, always available and the M2 default (D16). ``OpusEncoder``
(Ogg Opus via ``opuscodec``, D16) is opt-in with ``HEARNARRO_AUDIO_FORMAT=opus`` and the
``opus`` extra; without the package it reports itself unavailable and ``default_encoder("opus")``
falls back to WAV with a warning.
"""

from __future__ import annotations

import io
import logging
import wave
from typing import Protocol

log = logging.getLogger(__name__)


class EncoderUnavailable(RuntimeError):
    """The encoder's dependency (e.g. ``opuscodec``) is not installed."""


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
    """Ogg Opus via ``opuscodec`` (Apache-2.0, bundles libopus; D16).

    libopus accepts 8/12/16/24/48 kHz input natively, so the 24 kHz model output is encoded
    as-is (no resampling); the Ogg header records the input rate and decoders play at 48 kHz.
    48 kbps, mono, VOIP-agnostic signal type, complexity 10, QEXT off (smaller files; 277).
    """

    media_type = "audio/ogg"
    ext = "ogg"
    bitrate_bps = 48_000
    sample_rates = (8_000, 12_000, 16_000, 24_000, 48_000)

    def __init__(self) -> None:
        try:
            import opuscodec  # noqa: F401
        except ImportError as exc:
            raise EncoderUnavailable(
                "opuscodec is not installed (pip install -e '.[opus]')"
            ) from exc

    def encode(self, pcm: bytes, sample_rate: int) -> bytes:
        import numpy as np
        import opuscodec

        if len(pcm) % 2:
            raise ValueError("PCM16 buffer has an odd number of bytes")
        if sample_rate not in self.sample_rates:
            raise ValueError(f"Opus needs one of {self.sample_rates} Hz, got {sample_rate}")
        samples = np.frombuffer(pcm, dtype="<i2").astype(np.int16).reshape(-1, 1)
        if samples.size == 0:  # opuscodec refuses to flush an empty stream: one 20 ms silent frame
            samples = np.zeros((sample_rate // 50, 1), dtype=np.int16)
        enc = opuscodec.OpusBufferedEncoder(sample_rate, 1, bitrate=self.bitrate_bps, qext=False)
        try:
            out = enc.write(samples) + enc.flush()
        finally:
            enc.close()
        return bytes(out)


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
