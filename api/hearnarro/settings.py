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
WEB_DIST_ENV = "HEARNARRO_WEB_DIST"  # D21: built web app served at /
REPO_ROOT = Path(__file__).resolve().parents[2]
TRIM_LEAD_ENV = "HEARNARRO_TRIM_LEAD_MS"  # SYN-1: silence kept before a clip's first sound
TRIM_TAIL_ENV = "HEARNARRO_TRIM_TAIL_MS"  # SYN-1: silence kept after its last sound
DEFAULT_TRIM_LEAD_MS = 60
DEFAULT_TRIM_TAIL_MS = 150
AUDIO_FORMATS = ("wav", "opus")  # D16: opus default (decided 2026-10-17)
DEFAULT_LOOKAHEAD = 5
BACKENDS = ("fake", "kokoro")
# D15: hexgrad/Kokoro-82M revision used when HEARNARRO_TTS_BACKEND=kokoro names no revision.
DEFAULT_KOKORO_REVISION = "f3ff3571791e39611d31c381e3a41a3af07b4987"
# D31/D34: speech recogniser for the tier-1 evals (EVAL-5/6) only; never used by the app.
# MIT-licensed CTranslate2 build of Whisper base, pinned like every Hugging Face model.
ASR_MODEL_REPO = "Systran/faster-whisper-base"
ASR_MODEL_REVISION = "ebe41f70d5b6dfa9166e2c581c45c9c0cfc57b66"
# Import names of the `tts` extra (D15: no `kokoro` package; model code is vendored).
TTS_MODULES = ("torch", "transformers", "misaki", "spacy", "inflect")


class SettingsError(ValueError):
    """An environment variable holds a value the app cannot run with."""


@dataclass(frozen=True)
class Settings:
    tts_backend: str  # "fake" | "kokoro"
    kokoro_revision: str | None
    lookahead: int
    data_dir: Path
    audio_format: str = "opus"  # "wav" | "opus" (D16)
    trim_lead_ms: int = DEFAULT_TRIM_LEAD_MS
    trim_tail_ms: int = DEFAULT_TRIM_TAIL_MS


def kokoro_available() -> bool:
    """True when the ``tts`` extra is installed (``pip install -e '.[tts]'``)."""
    return all(importlib.util.find_spec(m) is not None for m in TTS_MODULES)


def _non_negative_int(env: Mapping[str, str], name: str, default: int) -> int:
    raw = env.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        value = int(raw)
    except ValueError:
        raise SettingsError(f"{name}={raw!r} is not an integer") from None
    if value < 0:
        raise SettingsError(f"{name}={raw!r} must be >= 0")
    return value


def trim_pads(env: Mapping[str, str] | None = None) -> tuple[int, int]:
    """(lead_ms, tail_ms) for the per-clip silence trim (SYN-1), from ``env``."""
    env = os.environ if env is None else env
    return (
        _non_negative_int(env, TRIM_LEAD_ENV, DEFAULT_TRIM_LEAD_MS),
        _non_negative_int(env, TRIM_TAIL_ENV, DEFAULT_TRIM_TAIL_MS),
    )


def load_settings(
    env: Mapping[str, str] | None = None, *, kokoro_installed: bool | None = None
) -> Settings:
    """Read settings from ``env`` (default ``os.environ``).

    Backend: an explicit ``HEARNARRO_TTS_BACKEND`` wins. ``kokoro`` takes
    ``HEARNARRO_KOKORO_REVISION``, defaulting to the D15 pin when the ``tts`` extra is
    installed (without the extra and without a revision it raises). Unset: ``kokoro`` when
    the extra is installed and a revision is set, else ``fake`` with a warning.
    """
    env = os.environ if env is None else env
    installed = kokoro_available() if kokoro_installed is None else kokoro_installed
    revision = env.get(KOKORO_REVISION_ENV) or None

    backend = (env.get(BACKEND_ENV) or "").strip().lower()
    if backend:
        if backend not in BACKENDS:
            raise SettingsError(f"{BACKEND_ENV}={backend!r}; expected one of {BACKENDS}")
        if backend == "kokoro" and revision is None:
            if not installed:
                raise SettingsError(
                    f"{BACKEND_ENV}=kokoro: the tts extra is not installed and no "
                    f"{KOKORO_REVISION_ENV} is set"
                )
            revision = DEFAULT_KOKORO_REVISION
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

    audio_format = (env.get(AUDIO_FORMAT_ENV) or "opus").strip().lower()
    if audio_format not in AUDIO_FORMATS:
        raise SettingsError(f"{AUDIO_FORMAT_ENV}={audio_format!r}; expected one of {AUDIO_FORMATS}")

    trim_lead_ms, trim_tail_ms = trim_pads(env)
    data_dir = resolve_data_dir(env.get(DATA_DIR_ENV) or None)
    return Settings(
        tts_backend=backend,
        kokoro_revision=revision,
        lookahead=lookahead,
        data_dir=data_dir,
        audio_format=audio_format,
        trim_lead_ms=trim_lead_ms,
        trim_tail_ms=trim_tail_ms,
    )


def web_dist_dir(env: Mapping[str, str] | None = None) -> Path | None:
    """D21: the built web app to serve at ``/``: ``$HEARNARRO_WEB_DIST``, else
    ``<repo>/web/dist``; None when that directory does not exist."""
    env = os.environ if env is None else env
    raw = (env.get(WEB_DIST_ENV) or "").strip()
    path = Path(raw).expanduser() if raw else REPO_ROOT / "web" / "dist"
    return path if path.is_dir() else None
