# YomiKoe

A Speechify-style reader: drop in a PDF, pick a voice and a speed, and listen with the text highlighted as it plays. Self-hosted, backed by open TTS models, built so the synthesis engine can be swapped without touching the reader.

Domains (D52, plan of 2026-10-21): [yomikoe.app](https://yomikoe.app) is the brand domain and landing page (static site, `site/`, deployed by GitHub Pages; see docs/HOSTING.md); app.yomikoe.app will serve the reader (`web/`); api.yomikoe.app the API (`api/`); getyomikoe.com is a defensive .com that 301-redirects to yomikoe.app and is never printed. Until M9 Hosting, everything runs locally via Docker Compose; the table in `docs/PRD.md` ("Domains") is the source of truth.

The product spec lives in [docs/PRD.md](docs/PRD.md) and the technical design in [docs/TECHNICAL_DESIGN.md](docs/TECHNICAL_DESIGN.md). Requirement IDs there (`ING-`, `SYN-`, `PLAY-`, `LIB-`) are canonical and referenced in commits and tests.

## Layout

```
api/            FastAPI service (Python 3.11+)
  yomikoe/
    ingestion/  PDF -> blocks -> reading order -> sentence segments   (ING-*)
    synthesis/  TTSBackend interface, Kokoro backend, cache, queue   (SYN-*)
    storage/    SQLite models and file paths                          (LIB-*)
    routes/     REST + WebSocket endpoints
  tests/        pytest; fixtures/pdfs holds the 20-PDF gate set
web/            React + TypeScript reader (Vite)                      (PLAY-*)
scripts/        benchmarks, fixture tooling
docs/           PRD and design notes
```

## Milestones

| | Scope | Gate |
| --- | --- | --- |
| M1 | Ingest + skeleton | 20 fixture PDFs parse in correct reading order |
| M2 | Synthesis + stream | first audio < 2 s at 0.5x–3x on CPU |
| M3 | Reader UI | highlight drift < 1 word over 10 min |
| M4 | Library + polish | 300-page soak passes; `docker compose up` works |

## Quickstart (M1)

M1 ingests PDFs into ordered sentence segments; there is no audio or UI yet.

```bash
cd api
.venv/bin/python -m yomikoe serve --data-dir ~/yomikoe-m1 --port 8765   # terminal 1
.venv/bin/python scripts/m1_smoke.py --base-url http://127.0.0.1:8765        # terminal 2
.venv/bin/python scripts/m1_smoke.py --one path/to/your.pdf                   # any PDF
```

The smoke script uploads the 15 text fixtures, scores them with the gate's word-level
measure, and exits 0 when all pass (mean 0.9914 today). The full hand-testing procedure,
with the curl sequence and expected numbers, is in [docs/M1_TESTING.md](docs/M1_TESTING.md).

Audio (M2): `.venv/bin/python scripts/m1_smoke.py --audio` fetches audio for the first segments of every document (start the server with `YOMIKOE_TTS_BACKEND=kokoro` and the `tts` extra for real speech); the step-by-step check is [docs/M2_TESTING.md](docs/M2_TESTING.md).

## Getting started

```bash
cd api
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

Models download from the Hugging Face Hub on first run into `$HF_HOME`; set it to a persistent path. Audio is cached as WAV by default; `pip install -e ".[opus]"` and `YOMIKOE_AUDIO_FORMAT=opus` switch to Ogg Opus (no ffmpeg needed).

## Benchmark (M2)

`cd api && .venv/bin/python scripts/bench.py` (needs `uv pip install -e '.[dev,tts]'`) prints time to first audio and real-time factor for Kokoro over 20 fixture sentences at 0.5/1.0/2.0/3.0x and writes `bench/<date>.json`; latest: `bench/2026-10-16.json`.

## Documentation

- [docs/PRD.md](docs/PRD.md): scope, requirement IDs, milestone gates
- [docs/TECHNICAL_DESIGN.md](docs/TECHNICAL_DESIGN.md): algorithms, schema, protocol, decision log
- [docs/M1_TESTING.md](docs/M1_TESTING.md): M1 hand-testing procedure
- [docs/guide/](docs/guide/): milestone guides
- [docs/CODE_MAP_M1.md](docs/CODE_MAP_M1.md): M1 code map (flows, stage rules, golden and quality gates, modules, data structures)
- [docs/CODE_MAP_M2.md](docs/CODE_MAP_M2.md): M2 code map (flows, modules, data structures, concurrency, licences)

## Licence

Apache-2.0 (see [LICENSE](LICENSE)). Copyright 2026 Sowmya Jonnalagadda. Every dependency and model shipped in v1 is under Apache-2.0, MIT or BSD terms; `api/scripts/check_licences.py` enforces this in the test suite, and vendored components carry their own NOTICE files.
