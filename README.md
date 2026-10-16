# HearNarro

A Speechify-style reader: drop in a PDF, pick a voice and a speed, and listen with the text highlighted as it plays. Self-hosted, backed by open TTS models, built so the synthesis engine can be swapped without touching the reader.

The product spec lives in [docs/PRD.md](docs/PRD.md) and the technical design in [docs/TECHNICAL_DESIGN.md](docs/TECHNICAL_DESIGN.md). Requirement IDs there (`ING-`, `SYN-`, `PLAY-`, `LIB-`) are canonical and referenced in commits and tests.

## Layout

```
api/            FastAPI service (Python 3.11+)
  hearnarro/
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
.venv/bin/python -m hearnarro serve --data-dir ~/hearnarro-m1 --port 8765   # terminal 1
.venv/bin/python scripts/m1_smoke.py --base-url http://127.0.0.1:8765        # terminal 2
.venv/bin/python scripts/m1_smoke.py --one path/to/your.pdf                   # any PDF
```

The smoke script uploads the 15 text fixtures, scores them with the gate's word-level
measure, and exits 0 when all pass (mean 0.9914 today). The full hand-testing procedure,
with the curl sequence and expected numbers, is in [docs/M1_TESTING.md](docs/M1_TESTING.md).

## Getting started

```bash
cd api
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

Models download from the Hugging Face Hub on first run into `$HF_HOME`; set it to a persistent path. `ffmpeg` must be on PATH for the Opus audio cache.
