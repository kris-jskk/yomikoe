"""Environment settings (M2 spec "config"; SYN-4 backend choice, SYN-5 lookahead N)."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from yomikoe.settings import Settings, SettingsError, load_settings


def test_syn4_settings_defaults_fake_with_warning_when_kokoro_missing(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.WARNING, logger="yomikoe.settings"):
        s = load_settings({}, kokoro_installed=False)
    assert s == Settings(
        tts_backend="fake", kokoro_revision=None, lookahead=5, data_dir=Path("./data")
    )
    assert any("fake" in r.getMessage() for r in caplog.records)


def test_syn4_settings_default_kokoro_only_when_installed_and_pinned() -> None:
    assert load_settings({}, kokoro_installed=True).tts_backend == "fake"
    s = load_settings({"YOMIKOE_KOKORO_REVISION": "abc123"}, kokoro_installed=True)
    assert (s.tts_backend, s.kokoro_revision) == ("kokoro", "abc123")


def test_syn4_settings_explicit_backend() -> None:
    assert load_settings({"YOMIKOE_TTS_BACKEND": "fake"}, kokoro_installed=True).tts_backend == (
        "fake"
    )
    env = {"YOMIKOE_TTS_BACKEND": "kokoro", "YOMIKOE_KOKORO_REVISION": "deadbeef"}
    assert load_settings(env, kokoro_installed=False).tts_backend == "kokoro"


@pytest.mark.parametrize(
    "env",
    [
        {"YOMIKOE_TTS_BACKEND": "kokoro"},  # revision required
        {"YOMIKOE_TTS_BACKEND": "espeak"},
        {"YOMIKOE_LOOKAHEAD": "five"},
        {"YOMIKOE_LOOKAHEAD": "-1"},
        {"YOMIKOE_AUDIO_FORMAT": "mp3"},
    ],
)
def test_syn4_settings_invalid_values_raise(env: dict[str, str]) -> None:
    with pytest.raises(SettingsError):
        load_settings(env, kokoro_installed=False)


def test_syn5_settings_lookahead_and_data_dir_from_env(tmp_path: Path) -> None:
    env = {"YOMIKOE_LOOKAHEAD": "3", "YOMIKOE_DATA_DIR": str(tmp_path)}
    s = load_settings(env, kokoro_installed=False)
    assert s.lookahead == 3
    assert s.data_dir == tmp_path


def test_syn1_settings_audio_format_opus_default_wav_opt_in() -> None:
    assert load_settings({}, kokoro_installed=False).audio_format == "opus"  # D16
    env = {"YOMIKOE_AUDIO_FORMAT": "wav"}
    assert load_settings(env, kokoro_installed=False).audio_format == "wav"
