"""KokoroBackend: the only module that names a TTS model (SYN-4).

``hexgrad/Kokoro-82M`` (Apache-2.0), revision pinned via ``HEARNARRO_KOKORO_REVISION``.
Package and phonemizer are the M2 survey's choice. Stub until then; nothing imports it
except the app's backend factory (when configured) and the ``@pytest.mark.model`` tests.
"""

from __future__ import annotations

from hearnarro.synthesis.backend import SynthResult, Voice

MODEL_REPO = "hexgrad/Kokoro-82M"


class KokoroBackend:
    name = "kokoro"

    def __init__(self, revision: str) -> None:
        self.revision = revision

    def voices(self) -> list[Voice]:
        raise NotImplementedError

    def speed_range(self) -> tuple[float, float]:
        raise NotImplementedError

    def synthesize(self, text: str, voice_id: str, speed: float) -> SynthResult:
        raise NotImplementedError
