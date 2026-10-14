# HearNarro — instructions for coding sessions

- Read `docs/PRD.md` before any task. It is the source of truth for scope, requirement IDs, data model, API shape and milestone gates.
- Requirement IDs (`ING-n`, `SYN-n`, `PLAY-n`, `LIB-n`) are canonical. Reference them in commit messages, test names and PR descriptions. Never rename or renumber them.
- Work milestone by milestone (M1 → M4). Do not start a later milestone until the previous gate test passes.
- Write the gate test before the feature. Gate tests live in `api/tests/` and are the acceptance criteria.
- `TTSBackend` (see PRD, "Data model and API") is the only place a TTS model may be named. The reader and API never import a model directly.
- Licensing: every dependency and model in v1 must be Apache-2.0, MIT or BSD. No non-commercial models in shipped code.
- Pin every Hugging Face model to a revision hash in config.
- Python: 3.11+, `ruff` for lint/format, `pytest` for tests, type hints everywhere.
- Frontend: React + TypeScript + Vite in `web/`. Audio playback uses Media Source Extensions, not per-segment `<audio>` tags.
- Keep `docs/PRD.md` in sync with decisions. If a decision in code departs from the PRD, update the PRD in the same PR.
