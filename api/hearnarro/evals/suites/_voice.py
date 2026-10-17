"""One Kokoro voice per eval run, rendered the way the service renders a segment (EVAL-5,
EVAL-6, EVAL-7; SYN-1, SYN-4; D6, D17, D31).

``backend()`` constructs ``KokoroBackend`` once with the pinned revision (D15) and warms it.
``render`` mirrors ``SynthesisService._render``: synthesize at ``min(speed, native max)``,
cut leading/trailing silence to the configured pads (SYN-1, ``trim.trim_silence``), and above
the native maximum time-stretch the PCM and scale the timestamps (``stretch.py``), clamped to
the new duration. ``roundtrip`` renders once per (text, voice, speed) and transcribes the
audio with the recogniser; it is cached so EVAL-5 and EVAL-6 share one synthesis and one
transcription per example. Only the timestamps and recognised words are kept, not the audio.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from functools import cache
from typing import Any

from hearnarro.evals.suites import _asr


@dataclass(frozen=True)
class Roundtrip:
    duration_ms: int
    timestamps: tuple[Any, ...]  # hearnarro.synthesis.backend.WordTimestamp
    asr: tuple[_asr.AsrWord, ...]


def unavailable() -> str | None:
    """Why the voice cannot run here, or None (the ``tts`` extra is needed)."""
    from hearnarro.settings import kokoro_available

    if not kokoro_available():
        return "Kokoro unavailable: pip install -e '.[tts]'"
    return None


@cache
def backend() -> Any:
    """The run's KokoroBackend at the pinned revision, warmed with one short synthesis."""
    from hearnarro.settings import DEFAULT_KOKORO_REVISION
    from hearnarro.synthesis.kokoro_backend import KokoroBackend

    b = KokoroBackend(revision=DEFAULT_KOKORO_REVISION)
    b.synthesize("Warm up the model.", b.voices()[0].id, 1.0)
    return b


def render(text: str, voice: str, speed: float) -> Any:
    """SynthResult for ``text`` at ``speed``, through the service's trim and stretch path."""
    from hearnarro.settings import trim_pads
    from hearnarro.synthesis.backend import SynthResult
    from hearnarro.synthesis.stretch import scale_timestamps, stretch_pcm
    from hearnarro.synthesis.trim import trim_silence

    b = backend()
    native = min(speed, b.speed_range()[1])
    res = b.synthesize(text, voice, native)
    lead, tail = trim_pads()
    pcm, ts = trim_silence(res.audio, res.sample_rate, res.timestamps, lead_ms=lead, tail_ms=tail)
    if speed > native:
        ratio = speed / native
        pcm = stretch_pcm(pcm, res.sample_rate, ratio)
        dur = int((len(pcm) // 2) * 1000 / res.sample_rate)
        ts = [
            dataclasses.replace(
                t, start_ms=min(t.start_ms, min(t.end_ms, dur)), end_ms=min(t.end_ms, dur)
            )
            for t in scale_timestamps(ts, ratio)
        ]
    return SynthResult(audio=pcm, sample_rate=res.sample_rate, timestamps=list(ts))


@cache
def roundtrip(text: str, voice: str, speed: float) -> Roundtrip:
    """Render then transcribe, once per (text, voice, speed) per process."""
    res = render(text, voice, speed)
    words = _asr.transcribe(res.audio, res.sample_rate)
    return Roundtrip(res.duration_ms, tuple(res.timestamps), tuple(words))
