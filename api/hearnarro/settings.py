"""Runtime configuration from environment variables (M2 spec "config")."""

from __future__ import annotations

import importlib.util
import logging
import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from hearnarro.storage.db import resolve_data_dir

log = logging.getLogger(__name__)

BACKEND_ENV = "HEARNARRO_TTS_BACKEND"
KOKORO_REVISION_ENV = "HEARNARRO_KOKORO_REVISION"
LOOKAHEAD_ENV = "HEARNARRO_LOOKAHEAD"
DATA_DIR_ENV = "HEARNARRO_DATA_DIR"
AUDIO_FORMAT_ENV = "HEARNARRO_AUDIO_FORMAT"
AUDIO_FORMATS = ("wav", "opus")  # D16: wav default
DEFAULT_LOOKAHEAD = 5
BACKENDS = ("fake", "kokoro")


class SettingsError(ValueError):
    """An environment variable holds a value the app cannot run with."""


@dataclass(frozen=True)
class Settings:
    tts_backend: str  # "fake" | "kokoro"
    kokoro_revision: str | None
    lookahead: int
    data_dir: Path
    audio_format: str = "wav"  # "wav" | "opus" (D16)


def kokoro_available() -> bool:
    return importlib.util.find_spec("kokoro") is not None


def load_settings(
    env: Mapping[str, str] | None = None, *, kokoro_installed: bool | None = None
) -> Settings:
    """Read settings from ``env`` (default ``os.environ``).

    Backend: an explicit ``HEARNARRO_TTS_BACKEND`` wins (``kokoro`` then requires
    ``HEARNARRO_KOKORO_REVISION``). Unset: ``kokoro`` when the package is installed and a
    revision is pinned, else ``fake`` with a warning.
    """
    env = os.environ if env is None else env
    installed = kokoro_available() if kokoro_installed is None else kokoro_installed
    revision = env.get(KOKORO_REVISION_ENV) or None

    backend = (env.get(BACKEND_ENV) or "").strip().lower()
    if backend:
        if backend not in BACKENDS:
            raise SettingsError(f"{BACKEND_ENV}={backend!r}; expected one of {BACKENDS}")
        if backend == "kokoro" and revision is None:
            raise SettingsError(f"{BACKEND_ENV}=kokoro requires {KOKORO_REVISION_ENV}")
    elif installed and revision is not None:
        backend = "kokoro"
    else:
        backend = "fake"
        log.warning(
            "TTS backend: fake (kokoro %s); set %s to choose",
            "has no pinned revision" if installed else "not installed",
            BACKEND_ENV,
        )

    raw = env.get(LOOKAHEAD_ENV)
    if raw is None or raw.strip() == "":
        lookahead = DEFAULT_LOOKAHEAD
    else:
        try:
            lookahead = int(raw)
        except ValueError:
            raise SettingsError(f"{LOOKAHEAD_ENV}={raw!r} is not an integer") from None
        if lookahead < 0:
            raise SettingsError(f"{LOOKAHEAD_ENV}={raw!r} must be >= 0")

    audio_format = (env.get(AUDIO_FORMAT_ENV) or "wav").strip().lower()
    if audio_format not in AUDIO_FORMATS:
        raise SettingsError(f"{AUDIO_FORMAT_ENV}={audio_format!r}; expected one of {AUDIO_FORMATS}")

    data_dir = resolve_data_dir(env.get(DATA_DIR_ENV) or None)
    return Settings(
        tts_backend=backend,
        kokoro_revision=revision,
        lookahead=lookahead,
        data_dir=data_dir,
        audio_format=audio_format,
    )
