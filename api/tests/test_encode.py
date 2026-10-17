"""Encoders for the browser (D7; SYN-1 audio delivery)."""

from __future__ import annotations

import io
import math
import struct
import wave

import pytest

from hearnarro.synthesis.encode import AudioEncoder, WavEncoder, default_encoder

SR = 24_000


def one_second_tone() -> bytes:
    return b"".join(
        struct.pack("<h", int(8000 * math.sin(2 * math.pi * 440 * i / SR))) for i in range(SR)
    )


def test_syn1_wav_encoder_header_24khz_mono_16bit_data_length() -> None:
    pcm = one_second_tone()
    out = WavEncoder().encode(pcm, SR)
    assert out[:4] == b"RIFF" and out[8:12] == b"WAVE"
    with wave.open(io.BytesIO(out), "rb") as w:
        assert w.getframerate() == 24_000
        assert w.getnchannels() == 1
        assert w.getsampwidth() == 2
        assert w.getnframes() == SR
        assert w.readframes(SR) == pcm
    data_at = out.index(b"data")
    assert struct.unpack("<I", out[data_at + 4 : data_at + 8])[0] == len(pcm) == 48_000


def test_syn1_wav_encoder_media_type_and_empty_input() -> None:
    enc = WavEncoder()
    assert (enc.media_type, enc.ext) == ("audio/wav", "wav")
    with wave.open(io.BytesIO(enc.encode(b"", SR)), "rb") as w:
        assert w.getnframes() == 0
    with pytest.raises(ValueError):
        enc.encode(b"\x00", SR)


def test_syn1_default_encoder_is_wav_d16() -> None:
    enc: AudioEncoder = default_encoder()
    assert isinstance(enc, WavEncoder)
    assert len(enc.encode(b"\x00\x00" * 240, SR)) == 44 + 480


def test_syn1_default_encoder_opus_requested_is_ogg_or_wav_fallback() -> None:
    enc = default_encoder("opus")
    assert (enc.media_type, enc.ext) in {("audio/ogg", "ogg"), ("audio/wav", "wav")}


def test_syn1_opus_encoder_ogg_container_and_size_d16() -> None:
    pytest.importorskip("opuscodec")
    from hearnarro.synthesis.encode import OpusEncoder

    enc = OpusEncoder()
    assert (enc.media_type, enc.ext) == ("audio/ogg", "ogg")
    pcm = one_second_tone()
    out = enc.encode(pcm, SR)
    assert out[:4] == b"OggS"
    assert b"OpusHead" in out[:200]
    wav_size = len(WavEncoder().encode(pcm, SR))
    assert len(out) < 0.2 * wav_size, (len(out), wav_size)
    with pytest.raises(ValueError):
        enc.encode(b"\x00", SR)
    assert enc.encode(b"", SR)[:4] == b"OggS"  # empty segment still yields a valid stream


def test_syn1_default_encoder_opus_when_installed_d16() -> None:
    pytest.importorskip("opuscodec")
    from hearnarro.synthesis.encode import OpusEncoder

    assert isinstance(default_encoder("opus"), OpusEncoder)
