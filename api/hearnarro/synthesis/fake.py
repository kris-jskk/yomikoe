"""FakeBackend: a deterministic TTSBackend for tests (SYN-1, SYN-2, SYN-4).

No model is involved. Each whitespace-separated word becomes ``80 ms / speed`` of silence at
24 kHz, words back to back, so every duration and timestamp is known in advance.
"""

from __future__ import annotations

import re

from hearnarro.synthesis.backend import SynthContext, SynthResult, Voice, WordTimestamp

SAMPLE_RATE = 24_000
WORD_MS = 80
_WORD = re.compile(r"\S+")

_VOICES = [
    Voice(id="fake_f1", name="Fake Female 1", backend="fake", language="en-US", gender="female"),
    Voice(id="fake_f2", name="Fake Female 2", backend="fake", language="en-US", gender="female"),
    Voice(id="fake_f3", name="Fake Female 3", backend="fake", language="en-US", gender="female"),
    Voice(id="fake_m1", name="Fake Male 1", backend="fake", language="en-US", gender="male"),
    Voice(id="fake_m2", name="Fake Male 2", backend="fake", language="en-US", gender="male"),
    Voice(id="fake_m3", name="Fake Male 3", backend="fake", language="en-US", gender="male"),
]


def frames_per_word(speed: float) -> int:
    """Frames of silence per word at ``speed`` (80 ms / speed at 24 kHz)."""
    return round(SAMPLE_RATE * WORD_MS / 1000 / speed)


class FakeBackend:
    name = "fake"

    def voices(self) -> list[Voice]:
        return list(_VOICES)

    def speed_range(self) -> tuple[float, float]:
        return (0.5, 2.0)

    def synthesize(
        self, text: str, voice_id: str, speed: float, context: SynthContext | None = None
    ) -> SynthResult:
        """``context`` is accepted and ignored (the fake does not phonemize)."""
        if voice_id not in {v.id for v in _VOICES}:
            raise ValueError(f"unknown voice {voice_id!r} for backend 'fake'")
        lo, hi = self.speed_range()
        if not lo <= speed <= hi:
            raise ValueError(f"speed {speed} outside the native range {lo}..{hi}")
        words = list(_WORD.finditer(text))
        if not words:
            return SynthResult(audio=b"", sample_rate=SAMPLE_RATE, timestamps=[])
        fpw = frames_per_word(speed)
        timestamps = [
            WordTimestamp(
                word=m.group(0),
                start_ms=i * fpw * 1000 // SAMPLE_RATE,
                end_ms=(i + 1) * fpw * 1000 // SAMPLE_RATE,
                char_start=m.start(),
                char_end=m.end(),
            )
            for i, m in enumerate(words)
        ]
        audio = b"\x00\x00" * (fpw * len(words))
        return SynthResult(audio=audio, sample_rate=SAMPLE_RATE, timestamps=timestamps)
