"""Generate tone.wav / tone.ogg (1 s, 440 Hz, PCM16 mono, 24 kHz) with the API's encoders."""

import math
import struct
from pathlib import Path

from yomikoe.synthesis.encode import EncoderUnavailable, OpusEncoder, WavEncoder

out, sr = Path(__file__).resolve().parent, 24_000
pcm = b"".join(
    struct.pack("<h", int(12000 * math.sin(2 * math.pi * 440 * i / sr)))
    for i in range(sr)
)
(out / "tone.wav").write_bytes(WavEncoder().encode(pcm, sr))
try:
    (out / "tone.ogg").write_bytes(OpusEncoder().encode(pcm, sr))
except EncoderUnavailable as exc:
    print("tone.ogg not generated:", exc)
print(sorted((p.name, p.stat().st_size) for p in out.glob("tone.*")))
