# HearNarro — instructions for coding sessions

- Read `docs/PRD.md` (what) and `docs/TECHNICAL_DESIGN.md` (how) before any task. The PRD is the source of truth for scope, requirement IDs and milestone gates; the Technical Design is the source of truth for algorithms, schema, protocol and the decision log (D1–D11).
- Requirement IDs (`ING-n`, `SYN-n`, `PLAY-n`, `LIB-n`) are canonical. Reference them in commit messages, test names and PR descriptions. Never rename or renumber them.
- Work milestone by milestone (M1 → M4). Do not start a later milestone until the previous gate test passes.
- Write the gate test before the feature. Gate tests live in `api/tests/` and are the acceptance criteria.
- `TTSBackend` (see PRD, "Data model and API") is the only place a TTS model may be named. The reader and API never import a model directly.
- Licensing: every dependency and model in v1 must be Apache-2.0, MIT or BSD. No non-commercial models in shipped code.
- Pin every Hugging Face model to a revision hash in config.
- Python: 3.11+, `ruff` for lint/format, `pytest` for tests, type hints everywhere.
- Frontend: React + TypeScript + Vite in `web/`. Audio playback is per-segment HTTP fetch + Web Audio API scheduled buffers (D5); never MSE, never per-segment `<audio>` tags. Player state is a typed `useReducer` machine in one file (D10).
- Audio cache is Opus/WebM via an ffmpeg subprocess (D7). Schema changes go through Alembic migrations.
- Keep `docs/PRD.md` in sync with decisions. If a decision in code departs from the PRD, update the PRD in the same PR.
