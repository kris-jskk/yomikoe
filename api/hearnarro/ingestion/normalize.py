"""Stage 5 normalization for speech, with a char_map back to the source (subset of ING-6)."""

from __future__ import annotations

SPOKEN_ACRONYMS = {"NASA", "JSON", "SQL", "NATO", "UNESCO", "RAM", "ROM", "GPU", "CPU"}


def normalize(text: str) -> tuple[str, list[int]]:
    """Return (normalized_text, char_map) with len(char_map) == len(normalized_text)."""
    raise NotImplementedError
