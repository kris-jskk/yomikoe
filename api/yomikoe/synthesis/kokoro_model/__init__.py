"""Kokoro-82M model code, vendored from ``kokoro`` 0.9.4 (Apache-2.0) per D15.

The PyPI ``kokoro`` package declares ``misaki[en]``, which pulls GPL/LGPL packages
(phonemizer, espeak, num2words). Only the four model files are copied here; the
upstream ``KPipeline`` is replaced by ``yomikoe.synthesis.kokoro_backend``.
Only ``kokoro_backend`` may import this package (TTSBackend rule).
"""

from .model import KModel

__all__ = ["KModel"]
