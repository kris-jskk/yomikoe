"""Licence shims for third-party imports (D15). See ``num2words``."""

from __future__ import annotations

import sys


def install() -> None:
    """Register our own modules under the names misaki imports. Call before ``import misaki.en``.

    ``misaki.en`` does ``from num2words import num2words`` at module top; the ``num2words``
    distribution is LGPL, so the name is served by ``yomikoe.synthesis.compat.num2words``.
    Idempotent; never overrides a module that is already registered under that name.
    """
    from yomikoe.synthesis.compat import num2words

    sys.modules.setdefault("num2words", num2words)
