```
TASK        m10-ext-prd
STATUS      done
ASSUMED     - Default API port is 8765, not the brief's 8000: docker-compose.yml maps "8765:8765" and docs/DOCKER.md says
              "The default host port is 8765" (1277). The spec uses http://localhost:8765.
            - Commit trailer uses "Claude Opus 5.5" (the harness's attribution for the model that ran), not the brief's
              "Claude Fable 5.1"; the brief's subject line is kept, with "EXT-1..18" filled in for "EXT-1..n".
            - Migration number 0007 (0006 is pronunciations); PRD_KINDLE's "0006" for D44 is stale (see OBSERVATIONS).
            - EXT numbering: client rows EXT-1..14, API rows EXT-15..18; the main PRD carries the 12 P0 rows.

RESULT      C1 @mozilla/readability licence is Apache-2.0 (v0.6.0, npm registry) — verified — 1275_readability_licence.txt
            C2 POST /documents rejects non-PDF with 415 (%PDF- magic in first 1024 bytes) and dedups by sha256 (200 + existing id) — verified — 1276_api_post_documents_accepts.txt
            C3 no CORS middleware in the API (no "cors" in api/yomikoe or api/pyproject.toml; no add_middleware in app.py) — verified — 1277_cors_grep.txt
            C4 default API host port in Docker Compose is 8765 (override file maps 8766 locally) — verified — 1277_cors_grep.txt
            C5 web/src/player: machine, schedule, skip, blockSpeed, keys, pauses DOM-free; mediaSession uses navigator/document; usePlayer is a React hook with AudioContext, window/DOM and api/client — verified (grep-level) — 1278_web_player_files.txt

OBSERVATIONS
            - "final milestone" still appears outside the brief's files: README.md:5, site/index.html:282 ("part of the
              final milestone"), docs/guide/m9-hosting-map.html:70 and :333. Not edited (not owned). 1280.
            - The player reads X-Timestamps and X-Duration-Ms from GET /audio; a cross-origin client needs them in
              CORS expose_headers (written into EXT-17/D58). 1276.
            - docs/PRD_KINDLE.md proposes migration 0006 for D44; 0006 is now 0006_pronunciations.py. 1276.
            - schedule.ts and skip.ts import types from web/src/api/types, so the alias must cover that file too. 1278.
            - PRD_EXTENSION.md is 222 lines (brief target 250-400); lines are long table rows, all sections present.
            - The TD has two decision tables (D1-D51 at top, D45-D54 under "M6 decisions"); D55-D59 went into a new
              "M10 decisions" section after D54, and the intro sentence was extended.

EVIDENCE    _agent/results/1275_readability_licence.txt — npm view: name, version 0.6.0, license Apache-2.0, repo URL
            _agent/results/1276_api_post_documents_accepts.txt — 415/sha256 lines of documents.py, audio headers, migrations list, EXT/EVAL-12/D55/source_url unused before the task
            _agent/results/1277_cors_grep.txt — no cors hits; FastAPI() with no middleware; compose ports 8765; DOCKER.md default port
            _agent/results/1278_web_player_files.txt — player file sizes, imports, DOM/browser-global hits per file
            _agent/results/1279_diff_stat.txt — staged diff stat (3 files, +273/-10), EXT/D row counts, status showing evals/ untouched
            _agent/results/1280_grep_final_milestone.txt — remaining "final milestone" hits are historical-date wording only in PRD/TD

FILES WRITTEN     docs/PRD_EXTENSION.md (new)
                  docs/PRD.md
                  docs/TECHNICAL_DESIGN.md
                  _agent/results/1275..1280 (six files above)
                  _agent/reports/m10-ext-prd.md
FILES READ BEYOND THE BRIEF     docker-compose.yml, docker-compose.override.yml (port), web/vite.config.ts and web/src/api/client.ts (grep only), api/yomikoe/storage/migrations/versions/ (listing)

UNVERIFIED  All Chrome API facts (sidePanel from 114, sidePanel.open() gesture from 116, no AudioContext in MV3 service
            worker, chrome.offscreen AUDIO_PLAYBACK, host permissions bypassing CORS, CSS Custom Highlight API from 105,
            Firefox/Safari MV3 support) — written as "unverified; from the worker's knowledge" and listed as open questions.
            Whether api/scripts/check_licences.py covers npm deps — not checked, listed as open question.
            The ingest()/pages interface gap is quoted from PRD_KINDLE.md, not re-checked.
NOT DONE    none (guide and CODE_MAP_M10.md are deliberately not created, per the brief)
DRAFTS      none

OUTPUT      commit fda95f9 on main (local, not pushed)
            docs/PRD.md | 45 ++++++++--   docs/PRD_EXTENSION.md | 222 +++   docs/TECHNICAL_DESIGN.md | 16 +++-
            3 files changed, 273 insertions(+), 10 deletions(-)
            git status after commit: only the user's evals/listening/pending_2026-10-22_formula/sheet.md (M) and
            pending_2026-10-22_formula_v2/ (??) remain, unstaged.
```
