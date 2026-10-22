"""TTSBackend: the only place a TTS model may be named (PRD SYN-4).

Every synthesis engine (Kokoro, a GPU model, a remote Hugging Face endpoint)
implements this Protocol. The service layer handles speeds outside a backend's
native range by synthesizing at the edge of the range and time-stretching.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class Voice:
    id: str
    name: str
    backend: str
    language: str  # BCP-47, e.g. "en-US"
    gender: str  # "female" | "male" | "neutral"


@dataclass(frozen=True)
class WordTimestamp:
    word: str
    start_ms: int
    end_ms: int
    char_start: int  # offsets into the text passed to synthesize()
    char_end: int


@dataclass(frozen=True)
class SynthContext:
    """Document context for pronunciation (SYN-4): acronym definitions found at ingestion
    (``{"TED": "Transferable Erosion Deposit"}``, ING-6) and the user's pronunciation
    overrides (TERM-2): ``lexicon`` maps a lower-case word to a respelling, the global table
    merged under the document's. ``document_id`` is for logging.

    ``math_spans`` is per segment (SYN-4, MATH-1..4): ``(start, end)`` offsets into the text
    passed to ``synthesize`` that are mathematics (the whole of an equation segment; in a body
    segment the normalized offsets whose ``char_map`` source lies in a ``math_json`` range). A
    backend voices a single-letter variable there as the letter ("a" is /eɪ/, not the article).
    The audio cache key (D6) does not change: a segment's spans are fixed by its stored row."""

    acronyms: dict[str, str] = field(default_factory=dict)
    document_id: int | None = None
    lexicon: dict[str, str] = field(default_factory=dict)
    math_spans: tuple[tuple[int, int], ...] = ()


@dataclass
class SynthResult:
    audio: bytes  # PCM 16-bit mono
    sample_rate: int  # 24_000 for Kokoro
    timestamps: list[WordTimestamp] = field(default_factory=list)

    @property
    def duration_ms(self) -> int:
        frames = len(self.audio) // 2
        return int(frames * 1000 / self.sample_rate)


class TTSBackend(Protocol):
    name: str

    def voices(self) -> list[Voice]: ...

    def speed_range(self) -> tuple[float, float]:
        """Native speed range, e.g. (0.5, 2.0). Outside it the service time-stretches."""
        ...

    def synthesize(
        self, text: str, voice_id: str, speed: float, context: SynthContext | None = None
    ) -> SynthResult:
        """``context`` is optional document context; a backend may ignore it."""
        ...
