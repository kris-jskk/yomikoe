"""Sentence-boundary metric over the word stream (ING-5, SYN-1; M2 boundary truth).

The functions live in ``hearnarro.evals.scorers`` (D32) so the eval suites share them; this
module re-exports them so the boundary tests keep their imports.
"""

from hearnarro.evals.scorers import (
    _alignment,
    align_boundaries,
    boundaries,
    prf,
    sentence_words,
)

__all__ = ["_alignment", "align_boundaries", "boundaries", "prf", "sentence_words"]
