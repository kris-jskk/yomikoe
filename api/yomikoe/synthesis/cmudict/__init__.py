"""The CMU Pronouncing Dictionary as a second lexicon tier (SYN-4).

Vendored data (``cmudict.dict.gz``, BSD-style CMU licence in ``LICENSE``; provenance in
``NOTICE``). The PyPI ``cmudict`` package is GPL-3.0-or-later and is not used. Each line is
``word ARPABET...`` with optional ``word(2)`` variants and ``# comment``; ``load`` keeps the
first pronunciation per word, keyed lower case.
"""

from __future__ import annotations

import functools
import gzip
from importlib import resources


@functools.cache
def load() -> dict[str, list[str]]:
    """``{"about": ["AH0", "B", "AW1", "T"], ...}`` (first variant only; ~135k words)."""
    out: dict[str, list[str]] = {}
    raw = resources.files(__package__).joinpath("cmudict.dict.gz").read_bytes()
    for line in gzip.decompress(raw).decode("utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        word, *phones = line.split()
        if "(" not in word:
            out.setdefault(word, phones)
    return out
