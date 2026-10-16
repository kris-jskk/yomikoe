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

## Rule: the session supervises; fresh workers on the cheapest adequate model do the work

The interactive session is the supervisor. It gathers state, splits the work, writes briefs,
reviews what comes back, makes the judgment calls, and writes to the user. It does not read
long files end to end, run batches of commands, or build things itself. The standing rules
live in `_agent/` at the repo root: `worker-contract.md` (what every worker must and must not
do), `brief-template.md`, `report-template.md`, and `supervisor-log.md`.

1. **Never fork.** Delegate with `subagent_type: general-purpose` and an explicit `model`.
   A fork inherits the whole conversation and always runs on the supervisor's model, so its
   context starts at the size of the conversation and the cheaper-model option does not exist.
2. **Sonnet for mechanical work, Opus for building.** Re-runs, state checks, tallies,
   lookups, and drafts go to Sonnet. New code, tests, builds, reviews, and anything the user
   will read go to Opus. Root-cause attribution, review of every outward draft, and the
   final message stay with the supervisor.
3. **Briefs are self-contained.** Every brief starts by pointing the worker at
   `_agent/worker-contract.md`, and every fact in it is a file path, not a sentence from the
   conversation. Each brief lists the CLAIMS it must settle and a BUDGET of tool calls.
   Assign file ownership so parallel workers never write the same file; only the supervisor
   edits `CLAUDE.md` and the files under `_agent/`.
4. **Every claim in a report is backed by a saved run or labelled unverified.** Workers save
   command output under `_agent/results/` and cite the file; the supervisor opens two cited
   evidence files per report before using it. A number nobody ran is a guess and is written
   as one.
5. **Local git only.** Workers commit on a branch or in a worktree; nobody pushes, opens a
   PR, or touches anything outside the repo without the user asking for that specific action.
   Enforce it in the harness too: `.claude/settings.json` lists `git push` and every `gh pr` and
   `gh issue` under `permissions.ask` so they prompt regardless of who calls them.
6. **Record the cost from the transcripts, not the notification.** A SubagentStop hook runs
   a script that reads each subagent transcript and regenerates `_agent/token-ledger.md`:
   the model that actually answered, final prompt size, new tokens, cache reads, and output.
   The figure the harness reports at completion is the final prompt size, a context measure;
   never quote it as consumption.
7. **Corrections are logged.** When the session tells the user something that later turns
   out wrong, the correction goes in `_agent/supervisor-log.md` with what was assumed, what
   was true, and what would have caught it earlier.
