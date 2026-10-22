"""Speech recogniser for the tier-1 evals (EVAL-5, EVAL-6; D31, D34).

faster-whisper (MIT) with the CTranslate2 Whisper weights named and pinned in exactly one
place, ``yomikoe.settings.ASR_MODEL_REPO`` / ``ASR_MODEL_REVISION``. The recogniser is not a
TTS model and is never imported by the app; only the ``evals`` extra installs it. The model is
loaded lazily, once per process (``model()`` is cached), on CPU with int8 weights.
"""

from __future__ import annotations

import importlib.util
import io
import wave
from dataclasses import dataclass
from functools import cache
from typing import Any


@dataclass(frozen=True)
class AsrWord:
    word: str  # as the recogniser wrote it (leading space and punctuation included)
    start_ms: float
    end_ms: float


def unavailable() -> str | None:
    """Why the recogniser cannot run here, or None."""
    if importlib.util.find_spec("faster_whisper") is None:
        return "faster-whisper not installed: pip install -e '.[evals]'"
    return None


@cache
def model() -> Any:
    """The pinned WhisperModel (downloaded to the Hugging Face cache on first use)."""
    from faster_whisper import WhisperModel

    from yomikoe.settings import ASR_MODEL_REPO, ASR_MODEL_REVISION

    return WhisperModel(
        ASR_MODEL_REPO, device="cpu", compute_type="int8", revision=ASR_MODEL_REVISION
    )


def _wav(pcm: bytes, sample_rate: int) -> io.BytesIO:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(pcm)
    buf.seek(0)
    return buf


def transcribe(pcm: bytes, sample_rate: int) -> list[AsrWord]:
    """English words with start/end times in ms for PCM16 mono audio. The clip is resampled
    to 16 kHz by faster-whisper's own decoder (PyAV); greedy-free beam search (5), no VAD, no
    conditioning on earlier text, so every clip is transcribed independently."""
    from faster_whisper import decode_audio

    audio = decode_audio(_wav(pcm, sample_rate), sampling_rate=16_000)
    segments, _ = model().transcribe(
        audio,
        language="en",
        beam_size=5,
        word_timestamps=True,
        condition_on_previous_text=False,
        vad_filter=False,
    )
    return [
        AsrWord(w.word, w.start * 1000.0, w.end * 1000.0)
        for seg in segments
        for w in seg.words or []
    ]
