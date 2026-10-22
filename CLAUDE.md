# YomiKoe (formerly HearNarro) — instructions for coding sessions

- Read `docs/PRD.md` (what) and `docs/TECHNICAL_DESIGN.md` (how) before any task. The PRD is the source of truth for scope, requirement IDs and milestone gates; the Technical Design is the source of truth for algorithms, schema, protocol and the decision log (D1–D11).
- Requirement IDs (`ING-n`, `SYN-n`, `PLAY-n`, `LIB-n`) are canonical. Reference them in commit messages, test names and PR descriptions. Never rename or renumber them.
- Work milestone by milestone (M1 → M4). Do not start a later milestone until the previous gate test passes.
- Write the gate test before the feature. Gate tests live in `api/tests/` and are the acceptance criteria.
- `TTSBackend` (see PRD, "Data model and API") is the only place a TTS model may be named. The reader and API never import a model directly.
- Licensing: every dependency and model in v1 must be Apache-2.0, MIT or BSD; transitive components under
  other OSI-approved non-copyleft licences (PSF-2.0, ISC, MPL-2.0 file-level, BSL-1.0, Zlib, CC0) are
  acceptable (clarified 2026-10-16). Copyleft (GPL, LGPL, AGPL, SSPL) and non-commercial terms are excluded
  from shipped code, including transitive imports; `api/scripts/check_licences.py` enforces it in the suite.
- Pin every Hugging Face model to a revision hash in config.
- Python: 3.11+, `ruff` for lint/format, `pytest` for tests, type hints everywhere.
- Frontend: React + TypeScript + Vite in `web/`. Audio playback is per-segment HTTP fetch + Web Audio API scheduled buffers (D5); never MSE, never per-segment `<audio>` tags. Player state is a typed `useReducer` machine in one file (D10).
- Audio cache is Ogg Opus in process via `opuscodec` (D7, D16), WAV with `YOMIKOE_AUDIO_FORMAT=wav`; no ffmpeg. Schema changes go through Alembic migrations.
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
   the model that actually answered, final prompt size, new tokens, cache reads, output, and
   an estimated cost in dollars from a rates table in the script (per model: input, output,
   cache write, cache read; source URL and date recorded next to the table). The ledger also
   carries the supervisor's own session usage, per-task and per-session totals, and a running
   total for the project. The figure the harness reports at completion is the final prompt
   size, a context measure; never quote it as consumption.
   **Review cadence:** at every milestone close, and whenever the user asks, the supervisor
   writes a "Cost review" section in the ledger: the ten most expensive tasks, what drove
   them (budget, re-runs, model, prompt size), and concrete changes for the next milestone
   (smaller briefs, Sonnet where adequate, fewer verification re-runs, shorter evidence
   files, tighter budgets). The review's actions become rules here when they prove out. Reviews
   live in `_agent/cost-reviews.md` (the ledger's own review table is regenerated by the script).
7. **Corrections are logged.** When the session tells the user something that later turns
   out wrong, the correction goes in `_agent/supervisor-log.md` with what was assumed, what
   was true, and what would have caught it earlier.
8. **Cost rules from review 1 (2026-10-17; two thirds of all spend was the supervisor re-reading a
   ~900k-token prefix on every tool call).**
   a. **Each milestone starts in a fresh session.** The handoff is on disk: this file, `docs/guide/`,
      `docs/CODE_MAP_*.md`, the memory directory, `_agent/token-ledger.md`, `_agent/cost-reviews.md`.
      When a milestone closes, the supervisor's closing message tells the user to start the next one
      in a new session and lists those handoff files. If the session prefix passes ~300k tokens
      mid-milestone, the supervisor says so at the next phase boundary and offers a fresh session.
   b. **Fewer supervisor tool calls.** One guide republish per phase, not per message; independent
      calls batched in one turn; a worker's saved verification is not re-run unless its evidence file
      is missing. Target: under 150 supervisor tool calls per milestone.
   c. **Worker budgets:** default 40 tool calls, cap 50 unless the brief says why more is needed;
      the two tasks that ran past 100 turns were the two most expensive worker tasks.
   d. **Sonnet for small tasks:** any task expected to take under ~15 tool calls (lookups, re-runs,
      tallies, test fixes with a known cause, doc tweaks) goes to Sonnet; Opus only for new code,
      reviews, and anything the user reads.

## Rule: every stage is visualized; the architectural guide tracks the phases

The published architectural guides are how the user follows the work, one per milestone:
M1 "YomiKoe M1 Ingest Map" https://claude.ai/artifact/NV2gGu1QaS7u68bmoGZ45n (closed; repo copy
`docs/guide/m1-ingest-map.html`), M2 "YomiKoe M2 Synthesis Map"
https://claude.ai/artifact/J7wJUWammFqBxc22s121Pr (source `m2-synthesis-map.html` in the session
scratchpad; copy under `docs/guide/` when the milestone closes), M5 "YomiKoe M5 Academic Map"
https://claude.ai/artifact/WMNfhRLczt5VtYWf9Pkt9r (source `docs/guide/m5-academic-map.html` in the repo,
published from there), M9 "YomiKoe M9 Hosting Map" https://claude.ai/artifact/6NF1qW6v5swKgudxq4ZBoA (source
`docs/guide/m9-hosting-map.html` in the repo, published from there; landing page preview
https://claude.ai/artifact/6kuWSEYniRTmXDh9udA7vq). Each new milestone starts a new guide.

1. **Every pipeline stage gets its own diagram** in the guide: the mechanism (what goes in,
   what rule is applied, what comes out), not a labelled box. A new stage, a replaced
   algorithm, or a new data shape between stages gets its diagram in the same change that
   introduces it. Diagrams are inline SVG, themed with `currentColor`, with a caption that
   states the claim the picture makes.
2. **The guide is updated at every major phase change**: when a phase starts, while it runs
   (if its status changes), and when it finishes. Each update carries a timestamp, the phase
   pills (done / running / next), the evidence produced (scores, counts, commit ids), and any
   decision taken. The supervisor republishes it before writing the user-facing message for
   that phase; a phase is not reported as closed until the guide says so.
3. **Why and not only what.** Each step in the guide says why it is necessary, in one or two
   sentences, and names the requirement ID or design decision it serves.
4. **A code map per milestone**, `docs/CODE_MAP_<milestone>.md`: the request and data flows end to end
   (one walkthrough per entry point), then every module and file with its responsibility, public
   functions, what it reads and writes, and a status (planned / stub / implemented / tested). It is
   updated in the same phase that lands or changes a module, and linked from the milestone's guide.

## Rule: evals are the trend line; gates are the floor (D31–D34, 2026-10-17)

- The eval layer lives in `api/yomikoe/evals/` (`docs/CODE_MAP_EVALS.md`); suites are `EVAL-1`..`EVAL-9`
  (PRD "Evals"); run records are committed under `evals/runs/` and `evals/runs/latest.json` points at the
  newest. Records are data: never edit one by hand.
- Before and after any change to `api/yomikoe/ingestion/`, `api/yomikoe/synthesis/` or the lexicon
  and acronym tables, run `api/.venv/bin/python -m yomikoe.evals run all --tier 0` (about 15 s) and cite
  the compare output (`python -m yomikoe.evals compare <baseline> <candidate>`) in the commit message or
  PR description. A regression (D33: a per-example drop over 0.01, 10 % on a timing, 1 on a count, or a
  new failure) is not a test failure, but an unexplained one blocks the merge in review.
- Tier 1 (`--tier 1`, real Kokoro plus faster-whisper, about 8 min) runs at every milestone close and once
  per backend when a `TTSBackend` is swapped; the scorecard of that run is linked from the milestone guide.
- `faster-whisper` is a development-only dependency (pyproject group `evals`), never imported by the
  app; the ASR model is named and pinned in `settings.py` only. No LLM-as-judge; no user data in datasets.
- Workers follow the same rule: a brief that touches ingestion or synthesis lists the tier-0 eval run under
  EVIDENCE.
