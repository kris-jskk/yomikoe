# M4 library + polish interfaces (supervisor-owned)

Branch `m4-library` from `main` (M3 merged at 5bb7f94, post-close fixes to 64271b2). Workers read this
file and the files it names; they do not read the conversation. Results numbering starts at 497.
Requirement IDs are canonical (`docs/PRD.md`); decisions D26–D30 below are proposed and become
Technical Design entries in phase 5 after the user confirms them.

## 0. Scope and gate

In scope (PRD "Milestones", item 4): LIB-1 library list, LIB-2 position persistence, LIB-3 remembered
voice/speed with a global default, LIB-4 delete; PLAY-6 keyboard, PLAY-7 Media Session, PLAY-8
skip-block toggles; ING-6 remaining number forms, ING-7 tables and equations as cues, ING-2 OCR
fallback, ING-8 sections written at ingestion (closes D25); FastAPI serves `web/dist` (D21);
Docker Compose; the 300-page soak gate. Carried: ING-4 page-marker lines, the document 17 findings,
D19 clause chunking (optional A/B), D16 (one play in the user's own Safari; user).

Out of scope: PLAY-9 export, the PDF page view (M5), virtualised rendering unless the soak demands it
(D29), iOS background playback (open question stays open; the muted `<audio>` workaround is not built).

**Gate** (PRD: "300-page soak passes; Docker up"):
1. API soak (`api/tests/test_soak_300.py`, `@pytest.mark.soak`, on with `YOMIKOE_TEST_SOAK=1`): a
   generated 300-page text PDF ingests to `ready` in under 300 s wall time on this laptop with peak RSS
   under 1.5 GB; every segment page returns in order; `/audio` serves the first and the last segment with
   `FakeBackend`; `DELETE` removes everything it created.
2. Browser soak (`web/tests/e2e/soak.spec.ts`, Chromium): the same document opens, first render under
   5 s, play with correct highlighted word at three probe times, skip to the last section, reload
   restores the position within one sentence.
3. Docker: `docker compose up --build` on a machine that has Docker, then `GET /documents` returns 200
   and the web app loads at `/`. Neither Docker nor any container runtime is installed on the dev
   machine (checked 2026-10-17: docker, podman, colima, orbstack, nerdctl all absent), so this clause is
   built and lint-checked here and run by the user, or by a worker after the user installs a runtime.

## 1. Server contract (phase 1)

Existing routes are unchanged in meaning: `POST /documents`, `GET /documents`, `GET /documents/{id}`,
`GET /documents/{id}/segments`, `GET /audio/{segment_id}`, `GET /voices` (`api/yomikoe/routes/`).
The `documents` table already has `voice_id`, `speed`, `position_segment_id`, `position_offset_ms`,
`last_opened_at`; the `settings` table exists (`docs/TECHNICAL_DESIGN.md` "Storage"). No migration is
needed for LIB-1..4 unless a worker finds a missing column; then Alembic `0004_*`.

| Change | Shape | Req |
| --- | --- | --- |
| `GET /documents` summary adds | `segment_count` (int), `position` `{segment_id, offset_ms}`, `progress` (float 0..1 = position segment's `order` / `segment_count`, 0 when no position), `settings` `{voice_id, speed}`, `last_opened_at` | LIB-1 |
| `GET /documents/{id}` adds | `segment_count`; `sections` now non-empty for documents ingested after ING-8 lands | LIB-1, ING-8 |
| `PATCH /documents/{id}` | JSON body, every key optional: `position: {segment_id, offset_ms}`, `settings: {voice_id, speed}` (either may be null to clear), `opened: true` sets `last_opened_at = now`. Returns the summary. 404 unknown document; 422 if `segment_id` is not one of the document's segments. Must accept `fetch(..., {keepalive: true})` from `pagehide` (D26) | LIB-2, LIB-3 |
| `DELETE /documents/{id}` | 204; deletes rows (cascade), `pdfs/{sha256}.pdf`, `audio/{id}/`; 404 unknown; 409 while `status == 'parsing'` | LIB-4 |
| `GET /settings`, `PUT /settings` | `{default_voice_id: str|null, default_speed: float}`; `default_speed` 1.25 when unset (user decision, M3 spec §6); PUT validates speed in [0.5, 3.0] | LIB-3 |
| Static web (D21) | `app.py` mounts `web/dist` (path from `YOMIKOE_WEB_DIST`, default `<repo>/web/dist` if it exists) at `/` with `html=True` AFTER the routers; `/documents`, `/audio`, `/voices`, `/settings` keep winning. No SPA fallback is needed: the client uses hash routes (`web/src/App.tsx`). When the directory is absent, `/` returns 404 and the API still serves | D21 |
| `yomikoe purge-audio --document-id N [--segment-id S] [--voice V] [--speed X]` | CLI (`api/yomikoe/cli.py`) deletes matching `audio_cache` rows and files; prints the count. For A/B measurements on the same segments (cost review 2, action 4) | D19 |
| ING-8 sections | Ingestion writes `sections` rows from heading blocks: `title` = block text, `level` = 1 for every heading in v1 (classify has no heading rank), `first_segment_id` = first segment of that block; segments carry `section_id`. `yomikoe renormalize` does not rebuild sections; a document ingested before this change keeps `sections` empty and the client keeps deriving them (D25) | ING-8 |

**D26 (proposed):** position saves go through the same `PATCH` as settings, sent with
`fetch(..., {keepalive: true})` on `pagehide`; `navigator.sendBeacon` is not used (it cannot send PATCH
or a JSON content type without a Blob workaround). One endpoint, one code path.

## 2. Client (phase 2)

Routes (existing hash router): `#/` library, `#/doc/{id}` reader. Files: `web/src/` as in
`docs/CODE_MAP_M3.md`; new `components/Library.tsx` replaces `Picker.tsx`, new `player/keys.ts` (keyboard map,
pure), `player/mediaSession.ts` (handlers, pure wrapper), `player/skip.ts` (skip rules, pure),
`api/client.ts` gains `patchDocument`, `deleteDocument`, `getSettings`, `putSettings`, `uploadDocument`.

| Feature | Behaviour | Req |
| --- | --- | --- |
| Library | Table: title, pages, progress %, last opened (relative), status; row click opens `#/doc/{id}`; upload control (`POST /documents`, shows parsing progress by polling `GET /documents/{id}` every 2 s until ready/failed); delete button with an inline confirm; global default voice and speed controls (`PUT /settings`) | LIB-1, LIB-3, LIB-4 |
| Position save | While playing, every 5 s and on every `PAUSE`, `PATCH position {segment_id, offset_ms}` where `offset_ms` is the audio time into the current sentence; `pagehide` sends the last known value with keepalive. Debounced so at most one request in flight; a failed save is retried at the next tick, never surfaced | LIB-2 |
| Position restore | On load, if `position.segment_id` is set, the reader scrolls to it and the first Play starts at that segment at `offset_ms` (clamped to the clip). `opened: true` is sent once per open | LIB-2 |
| Settings | On open: document `settings` if set, else `GET /settings` defaults. A voice or speed change in the reader `PATCH`es `settings` for that document (debounced 500 ms). The library's default controls never change an opened document's own settings | LIB-3 |
| Keyboard | One `keydown` listener on `document`: Space play/pause, `←`/`→` skip sentence, `Shift+←`/`Shift+→` skip section, `+`/`=` speed +0.25, `-` speed −0.25, clamped to [0.5, 3.0]. Ignored when the event target is an input, select, textarea or contenteditable | PLAY-6 |
| Media Session | `navigator.mediaSession` (feature-detected): metadata title = document title, artist "YomiKoe"; handlers play, pause, previoustrack, nexttrack map to the same dispatches as the keys; `playbackState` mirrors the machine. Lock-screen behaviour on a phone is a manual check | PLAY-7 |
| Skip toggles | Three toggles in `PlayerBar`: footnotes (segments whose block `type` is `footnote`), captions (`caption`), references (every segment from a heading whose text matches `/^(references|bibliography|works cited)\b/i` up to the next heading). Skipped segments are not scheduled, are rendered dimmed, and are jumped over by skip and seek. State lives in the machine (`skip: {footnotes, captions, references}`) and is persisted per document in `localStorage` (per-viewer convenience, wrapped in try/catch) | PLAY-8 |

The machine (`player/machine.ts`, D10) gains events `SET_SKIP`, `RESTORE_POSITION`, `TICK_SAVE`; the
reducer stays pure and the hook owns timers and fetches. Settings changes while `loading` (M3 deviation
6) are applied when the load finishes, not dropped.

## 3. Ingestion (phase 3)

| Change | Rule | Req |
| --- | --- | --- |
| Page markers | A block whose only text is a bracketed or bare number on its own line (`^\[?\d{1,4}\]?$`) outside the TOC region is typed `noise` (dropped), not body/list with empty normalized text. Golden fixtures updated; an existing document needs re-ingest (upload again), `renormalize` does not reclassify | ING-4 |
| Document 17 findings | TOC leakage: a heading whose text is a bare page number is `noise`; a heading fragment ending in a hyphen joins the next line of the same block; U+FB00..U+FB06 ligatures decompose in stage 1 like the existing ligature rule | ING-4, ING-5 |
| Number forms by ear | Before any rule: a sampler synthesizes the sentences in §3a with Kokoro to WAV files under `_agent/results/497_number_forms/` with an index. The user listens and marks which forms are wrong. Only those get normalizer rules, each with char-map round-trip tests like `test_ing6_*` | ING-6 |
| Tables | A `table` block becomes one cue segment "Table N, R rows." (N counts tables in the document) followed by one segment per row, cells joined with ", " and the row ended with "."; rows with no alphabetic character are skipped. Golden D14 excluded-mass check unchanged (table chars still excluded from prose comparison) | ING-7 |
| Equations | An `equation` block becomes one segment with text "Equation." (or "Equation N." when a label like `(3)` is on the block); its symbols are never spoken | ING-7 |
| OCR fallback | Stage 1 reports per page `text_chars` (non-space glyphs). A page with fewer than 20 and a rendered page whose ink coverage is above 0.5 % (pypdfium2 render at 100 dpi, grayscale, pixels under 128) is sent to `OCRBackend.recognize(page_image) -> list[OcrLine]` (text + bbox). Backends: `TesseractBackend` (subprocess `tesseract --psm 3 tsv`, Apache-2.0, present only if the binary is on PATH) and `FakeOCRBackend` (returns lines from a fixture). Absent engine: the page is left empty, `documents.ocr_skipped_pages` (new column, migration 0004) records the count, the log says so. The `scanned_0N` fixtures test the detection; the real-engine test is `@pytest.mark.ocr`, skipped unless `tesseract` is on PATH | ING-2 |

**3a. Sampler sentences (ING-6 by ear).** `The price rose from $1.10 to $2.` / `The deal is worth $50
million.` / `It was founded in 1999 and sold in 2005.` / `By 2026 about 100,000 users had joined.` /
`Support runs 24/7 across 3 regions.` / `She is the Founder/CEO of the company.` / `The ratio was 3/4
of the total.` / `Call 555-0123 between 9 and 5.` / `Version 2.0 shipped on 12 March 2024.` /
`Section 4.2 covers the 1980s.` / `Temperatures reached 40°C, a 15% rise.` / `Read pages 10-12 and
figure 3b.`

**D28 (proposed):** OCR engine is Tesseract as a subprocess behind `OCRBackend`; no OCR engine is a
Python dependency. Tesseract is not installed on the dev machine; the user picks how to install it
(Homebrew is the usual way; the project otherwise avoids it, D20) or leaves OCR untested beyond the
fake backend in M4.

## 4. Soak and packaging (phase 4)

- **Soak fixture.** `api/tests/soak_util.py` generates `soak_300.pdf` into a temp dir at test time with
  `reportlab` (BSD-3, dev dependency only): 300 pages, a heading every 10 pages, about 20 sentences per
  page of varied English prose (not one repeated sentence; vary nouns and numbers so segment texts
  differ). Not committed (size).
- **Measurements saved** under `_agent/results/`: parse wall time, peak RSS (`resource.getrusage`),
  segment count, browser first-render time, per-probe highlight results.
- **D29 (proposed, decided by the soak):** if first render exceeds 5 s or the probes fail from
  scroll jank, `Reader.tsx` renders a window of segments around the current one (own implementation,
  no new dependency); otherwise the M3 "load everything" stays.
- **Docker (D30, proposed):** with D21 the API serves the built app, so Compose runs one service, `api`,
  built from `api/Dockerfile` (python:3.11-slim, `pip install .[tts]`, Kokoro revision pinned from config,
  `HF_HOME` on the `hf_home` volume, `YOMIKOE_DATA_DIR=/data` on a bind mount, port 8765). A multi-stage
  build runs `npm ci && npm run build` in a `node:24` stage and copies `web/dist` into the image. The `web`
  service in the current `docker-compose.yml` is removed. The compose file and Dockerfiles are
  lint-checked here (`docker compose config` is not available; a worker validates YAML and shell syntax)
  and built by the user.
- **D19 A/B (optional, user's call):** `yomikoe purge-audio` then `web/scripts/measure_first_audio.mjs`
  on the same segments with and without clause chunking of the first sentence at speeds under 1.0.

## 5. Tests (write red first)

| File | Covers |
| --- | --- |
| `api/tests/test_lib_gate.py` | LIB-1 summary fields and progress; LIB-2 PATCH round trip, 422 foreign segment, 404; LIB-3 document settings, global defaults, speed bounds; LIB-4 delete removes rows, audio files, pdf, 409 while parsing; `opened` updates `last_opened_at` |
| `api/tests/test_static_web.py` | D21: with a temp dist dir `/` serves `index.html`, `/documents` still JSON; without it `/` is 404 |
| `api/tests/test_purge_cli.py` | purge-audio counts and file removal |
| `api/tests/test_ing8_sections.py` | sections rows and `section_id` after ingest of a fixture with headings |
| `api/tests/test_ing7_tables.py`, `test_ing2_ocr.py`, `test_ing4_page_markers.py`, additions to `test_ing6_normalize.py` | phase 3 rules above |
| `api/tests/test_soak_300.py` | gate clause 1 |
| `web/tests/unit/{keys,skip,machine,library}.test.ts` | key map; skip rules incl. references span; new events; progress formatting |
| `web/tests/e2e/library.spec.ts`, `persist.spec.ts`, `keys.spec.ts`, `skip.spec.ts`, `soak.spec.ts` | LIB-1/4 in the page; LIB-2/3 across a reload; PLAY-6; PLAY-8; gate clause 2 |

## 6. Files and ownership (parallel workers never share a file)

| Owner | Files |
| --- | --- |
| server-lib worker | `api/yomikoe/routes/documents.py`, `routes/settings.py` (new), `storage/repo.py`, `app.py`, `cli.py`, `ingestion/pipeline.py` (sections only), tests listed for phase 1 |
| client worker(s) | `web/src/**`, `web/tests/**` split by file in the briefs |
| ingestion worker | `api/yomikoe/ingestion/*`, `synthesis/compat/*`, golden fixtures, phase 3 tests |
| soak/packaging worker | `api/tests/soak_util.py`, `test_soak_300.py`, `api/Dockerfile`, `docker-compose.yml`, `web/tests/e2e/soak.spec.ts` |
| supervisor | this file, `CLAUDE.md`, `_agent/*.md`, `docs/PRD.md`, `docs/TECHNICAL_DESIGN.md` (sync task may edit on instruction) |

## 7. Phases and evidence

| Phase | What | Evidence |
| --- | --- | --- |
| 0 setup | branch, M3 leftovers committed (e22c758), this spec, guide artifact, number-forms sampler, environment report | `497_number_forms/`, `498_env.txt` |
| 1 server | red gate tests; LIB-1..4, settings, static (D21), purge CLI, ING-8; green; ruff | `50x_*` red, green, ruff |
| 2 client | red unit + e2e; Library, position, settings, keys, Media Session, skip toggles; green on Chromium; WebKit/Firefox reported | `51x_*` |
| 3 ingestion | sampler verdicts from the user; ING-4 markers + document 17 rules; ING-7; ING-2 interface; goldens green | `52x_*` |
| 4 soak + packaging | soak gate API + browser; D29; Dockerfiles + compose; D19 A/B if asked | `53x_*` |
| 5 docs + close | `docs/CODE_MAP_M4.md` (code task), PRD + TD sync D26–D30 (docs task), `docs/M4_TESTING.md`, cost review 3, guide to `docs/guide/`, merge | ledger, review |
