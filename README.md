# HearNarro

A Speechify-style reader: drop in a PDF, pick a voice and a speed, and listen with the text highlighted as it plays. Self-hosted, backed by open TTS models, built so the synthesis engine can be swapped without touching the reader.

The product spec lives in [docs/PRD.md](docs/PRD.md). Requirement IDs there (`ING-`, `SYN-`, `PLAY-`, `LIB-`) are canonical and referenced in commits and tests.

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

## Getting started

```bash
cd api
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

Models download from the Hugging Face Hub on first run into `$HF_HOME`; set it to a persistent path.
