"""Number-form sampler (ING-6 by ear): normalize sentences, synthesize each to WAV, write an index.

Usage (from api/): .venv/bin/python scripts/sample_sentences.py OUT_DIR [--backend kokoro|fake]
                    [--voice ID] [sentence ...]
"""

from __future__ import annotations

import argparse
import sys
import wave
from pathlib import Path

API = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API))

SENTENCES = [
    "The price rose from $1.10 to $2.",
    "The deal is worth $50 million.",
    "It was founded in 1999 and sold in 2005.",
    "By 2026 about 100,000 users had joined.",
    "Support runs 24/7 across 3 regions.",
    "She is the Founder/CEO of the company.",
    "The ratio was 3/4 of the total.",
    "Call 555-0123 between 9 and 5.",
    "Version 2.0 shipped on 12 March 2024.",
    "Section 4.2 covers the 1980s.",
    "Temperatures reached 40°C, a 15% rise.",
    "Read pages 10-12 and figure 3b.",
]


def make_backend(name: str):
    if name == "fake":
        from hearnarro.synthesis.fake import FakeBackend

        return FakeBackend()
    from hearnarro.settings import DEFAULT_KOKORO_REVISION
    from hearnarro.synthesis.kokoro_backend import KokoroBackend

    return KokoroBackend(revision=DEFAULT_KOKORO_REVISION)


def main(argv: list[str] | None = None) -> int:
    from hearnarro.ingestion.normalize import normalize
    from hearnarro.synthesis.encode import WavEncoder

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("out_dir")
    ap.add_argument("--backend", default="kokoro", choices=("kokoro", "fake"))
    ap.add_argument("--voice", default=None)
    ap.add_argument("sentences", nargs="*")
    args = ap.parse_args(argv)

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    backend = make_backend(args.backend)
    voice = args.voice or backend.voices()[0].id
    enc = WavEncoder()
    rows = [
        "| # | source | normalized | file | seconds |",
        "|---|--------|------------|------|---------|",
    ]
    for i, src in enumerate(args.sentences or SENTENCES, 1):
        text = normalize(src)[0]
        res = backend.synthesize(text, voice, 1.0)
        name = f"{i:02d}.wav"
        (out / name).write_bytes(enc.encode(res.audio, res.sample_rate))
        with wave.open(str(out / name)) as w:
            secs = w.getnframes() / w.getframerate()
        rows.append(f"| {i} | {src} | {text} | {name} | {secs:.2f} |")
        print(rows[-1])
    (out / "index.md").write_text(
        f"voice {voice}, backend {backend.name}, speed 1.0\n\n" + "\n".join(rows) + "\n"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
