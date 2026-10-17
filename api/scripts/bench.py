"""M2 benchmark (PRD M2, SYN-3, SYN-4): time to first audio and real-time factor.

Usage (from api/): .venv/bin/python scripts/bench.py [--backend kokoro|fake] [--n 20]
                    [--voice ID] [--out ../bench]

- Sentences: the first ``--n`` distinct body/list sentences of 80..200 characters taken
  round-robin from ``tests/fixtures/pdfs/*.expected.jsonl``, normalized like the service does.
- Speeds 0.5/1.0/2.0/3.0. Speeds above the backend's native maximum are synthesized at the
  maximum and time-stretched (``hearnarro.synthesis.stretch``), exactly the service path.
- Cold cache, warm model: no audio cache is involved; the model is loaded and warmed once.
  A segment is synthesized whole (no streaming), so TTFA = synthesis (+ stretch) wall time.
- RTF = wall time / audio duration. Cold start (imports + model load) is measured once.
Prints a table and writes ``<out>/<YYYY-MM-DD>.json``.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import platform
import statistics
import sys
import time
from pathlib import Path

API = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API))
FIXTURES = API / "tests" / "fixtures" / "pdfs"
SPEEDS = (0.5, 1.0, 2.0, 3.0)
TTFA_LIMIT_MS = 2000  # PRD M2 gate


def bench_sentences(n: int) -> list[str]:
    from hearnarro.ingestion.normalize import normalize

    per_file = []
    for f in sorted(FIXTURES.glob("*.expected.jsonl")):
        rows = [json.loads(line) for line in f.read_text().splitlines() if line.strip()]
        per_file.append(
            [
                r["text"]
                for r in rows
                if r["type"] in ("body", "list") and 80 <= len(r["text"]) <= 200
            ]
        )
    out: list[str] = []
    i = 0
    while len(out) < n and any(i < len(p) for p in per_file):
        for p in per_file:
            if i < len(p) and len(out) < n:
                s = normalize(p[i])[0]
                if s not in out:
                    out.append(s)
        i += 1
    return out


def make_backend(name: str):
    if name == "fake":
        from hearnarro.synthesis.fake import FakeBackend

        return FakeBackend()
    from hearnarro.settings import DEFAULT_KOKORO_REVISION
    from hearnarro.synthesis.kokoro_backend import KokoroBackend

    return KokoroBackend(revision=DEFAULT_KOKORO_REVISION)


def run_one(backend, text: str, voice: str, speed: float) -> tuple[float, float]:
    """(wall_ms, audio_ms) for one segment at ``speed``, via stretch above the native max."""
    from hearnarro.synthesis.stretch import stretch_pcm

    native = min(speed, backend.speed_range()[1])
    t0 = time.perf_counter()
    res = backend.synthesize(text, voice, native)
    pcm = res.audio
    if speed > native:
        pcm = stretch_pcm(pcm, res.sample_rate, speed / native)
    wall = (time.perf_counter() - t0) * 1000
    return wall, len(pcm) / 2 / res.sample_rate * 1000


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--backend", default="kokoro", choices=("kokoro", "fake"))
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--voice", default=None)
    ap.add_argument("--out", default=str(API.parent / "bench"))
    args = ap.parse_args(argv)

    t0 = time.perf_counter()
    backend = make_backend(args.backend)
    cold_start_s = time.perf_counter() - t0
    voice = args.voice or backend.voices()[0].id
    sentences = bench_sentences(args.n)
    backend.synthesize("Warm up the model.", voice, 1.0)

    rows = []
    for speed in SPEEDS:
        for i, s in enumerate(sentences):
            wall, audio = run_one(backend, s, voice, speed)
            rows.append(
                {"speed": speed, "i": i, "chars": len(s), "ttfa_ms": round(wall, 1),
                 "audio_ms": round(audio, 1), "rtf": round(wall / audio, 4)}
            )  # fmt: skip

    summary = []
    print(f"backend {backend.name} voice {voice} sentences {len(sentences)} "
          f"cold start {cold_start_s:.2f} s")  # fmt: skip
    print(f"{'speed':>5} {'n':>3} {'TTFA mean':>9} {'p50':>6} {'max':>6} {'RTF mean':>8} "
          f"{'max':>6} {'<=2s':>5}")  # fmt: skip
    for speed in SPEEDS:
        r = [x for x in rows if x["speed"] == speed]
        t = [x["ttfa_ms"] for x in r]
        f = [x["rtf"] for x in r]
        ok = sum(x <= TTFA_LIMIT_MS for x in t)
        summary.append(
            {"speed": speed, "n": len(r), "ttfa_mean_ms": round(statistics.mean(t), 1),
             "ttfa_p50_ms": round(statistics.median(t), 1), "ttfa_max_ms": max(t),
             "rtf_mean": round(statistics.mean(f), 4), "rtf_max": max(f), "within_2s": ok}
        )  # fmt: skip
        print(f"{speed:>5} {len(r):>3} {statistics.mean(t):>9.0f} {statistics.median(t):>6.0f} "
              f"{max(t):>6.0f} {statistics.mean(f):>8.3f} {max(f):>6.3f} {ok:>2}/{len(r)}")  # fmt: skip

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{dt.date.today().isoformat()}.json"
    path.write_text(
        json.dumps(
            {
                "date": dt.datetime.now().isoformat(timespec="seconds"),
                "machine": f"{platform.platform()} {platform.machine()} py{platform.python_version()}",
                "backend": backend.name,
                "revision": getattr(backend, "revision", None),
                "voice": voice,
                "cold_start_s": round(cold_start_s, 2),
                "ttfa_limit_ms": TTFA_LIMIT_MS,
                "summary": summary,
                "sentences": sentences,
                "rows": rows,
            },
            indent=2,
        )
        + "\n"
    )
    print(f"wrote {path}")
    return 0 if all(s["within_2s"] == s["n"] for s in summary) else 1


if __name__ == "__main__":
    sys.exit(main())
