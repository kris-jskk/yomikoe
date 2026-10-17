# HearNarro M4 code map: library, persistence, polish, OCR, soak, packaging

This document explains how the M4 additions work end to end and what every file M4 added or changed
does. It is written for an engineer joining the project who has read `docs/PRD.md` (what),
`docs/TECHNICAL_DESIGN.md` (how; D21, D25, D26–D30), `docs/CODE_MAP_M2.md` (the audio API) and
`docs/CODE_MAP_M3.md` (the reader, whose flows a–j this map extends rather than repeats).

The design the code was built against is `_agent/specs/m4-library-interfaces.md` (the spec). Where
the code and the spec differ, this map says what the code does and lists the difference under
"Spec deviations", with the worker report it came from.

## Scope and status

**As of commit `eadaef6`** on branch `m4-library` (`git log --oneline main..m4-library`: 22 commits,
`e22c758` … `eadaef6`; the last product-code commit is `6122dee`, OCR wired into `extract_pages`;
`eadaef6` adds the browser soak `web/tests/e2e/soak.spec.ts`). Updated on 2026-10-17. Commits
`e2473f3` and `f2a8e3e` (EVAL-1..9 requirements, D31–D34, E0 eval gate, red) are on the branch but
are not M4 library code and are not mapped here.

### What M4 adds

- **LIB-1** library page: title, pages, progress %, last opened, status, upload, delete.
- **LIB-2** position saved while playing, on pause and on `pagehide` (D26); restored on open.
- **LIB-3** per-document voice and speed, plus global defaults (`GET`/`PUT /settings`, 1.25 when unset).
- **LIB-4** delete: rows, PDF and audio cache; 409 while parsing.
- **PLAY-6** keyboard map; **PLAY-7** Media Session; **PLAY-8** skip toggles (footnotes, captions,
  references).
- **ING-8** `sections` rows and `segments.section_id` written at ingestion (closes D25 for new uploads).
- **ING-7** tables become a cue plus one segment per row; equations become one "Equation [N]." cue.
- **ING-4 / ING-5** page-marker blocks typed noise; heading lines ending in a hyphen join without a
  space; U+FB00–U+FB06 ligatures decomposed in stage 1.
- **ING-2** OCR fallback behind `OCRBackend` (D28); `documents.ocr_skipped_pages` (migration 0004).
- **D21** FastAPI serves `web/dist` at `/`; **D30** one-service Docker image and Compose file.
- **D19 tooling** `hearnarro purge-audio`; **ING-6 tooling** `api/scripts/sample_sentences.py`
  (number-form sampler; no normalizer rule landed in this range).
- The 300-page soak gate (API and browser).

### The gate

PRD "300-page soak passes; Docker up" (spec §0):

1. API soak, `api/tests/test_soak_300.py` with `HEARNARRO_TEST_SOAK=1`:
   `_agent/results/525_soak_api.txt` (300 pages, 6030 segments, upload-to-ready 6.89 s, peak RSS
   119 MB self / 80 MB children, `/audio` first and last 200, delete clean; 1 passed). Skipped without
   the variable: `_agent/results/526_soak_skipped.txt`.
2. Browser soak, `web/tests/e2e/soak.spec.ts` (Chromium): `_agent/results/542_soak_browser.txt`
   (first `.seg` visible 619 ms, three probes pass, skip to the last section, reload restores with
   delta 0 sentences; 1 passed). D29 is therefore decided "no virtualisation": first render is far
   under 5 s.
3. Docker: built and lint-checked only (`_agent/results/528_compose_yaml.txt`,
   `529_web_build_local.txt`, `530_dockerfile_paths.txt`). No container runtime exists on the dev
   machine, so `docker compose up --build` is **unverified**; the user runs it.

Other suites: server LIB/static/purge `_agent/results/503_server_green.txt` (20 passed); ING-8
`506_ing8_green.txt` (2 passed); OCR `547_ocr_wired.txt` (19 passed, 1 skipped: tesseract); full API
suite `548_phase3_full_suite.txt` (908 passed, 28 skipped); web unit `514_unit_green.txt` (149 passed,
6 files); e2e Chromium `519_e2e_chromium_green.txt` (20 passed), WebKit `544_e2e_webkit_all.txt` and
Firefox `545_e2e_firefox_all.txt` (20 passed, 1 skipped each).

### Status words

| Word | Meaning |
| --- | --- |
| implemented | Real code; exercised only indirectly or by hand. |
| tested | Real code plus a passing saved run that exercises it. |
| unverified | Built, but the run that would show it working has not happened (no runtime / no binary / no device). |
| fixture | Test data or test harness, not shipped. |
| script | A command-line tool, not shipped in the bundle. |

### Status at a glance

| Piece | Status |
| --- | --- |
| `routes/documents.py` (summary, PATCH, DELETE), `routes/settings.py`, `storage/repo.py` additions | tested (503, 525) |
| `app.py` static mount, `settings.web_dist_dir` (D21) | tested (`test_static_web.py`, 503) |
| `cli.py` `purge-audio` | tested (`test_purge_cli.py`, 503) |
| `storage/jobs.py` sections + `ocr_skipped_pages` | tested (506, 538, 548) |
| `ingestion/ocr.py` with `FakeOCRBackend` | tested (547); `TesseractBackend` against a real binary: unverified |
| `ingestion/classify.py`, `merge.py`, `segment.py`, `extract.py`, `models.py` changes | tested (534, 535, 548) |
| `web/src/components/Library.tsx`, `libraryFormat.ts` | tested (unit `library.test.ts`, e2e `library.spec.ts`) |
| `player/keys.ts`, `skip.ts`, `machine.ts` additions | tested (unit 514; e2e `keys.spec.ts`, `skip.spec.ts`) |
| `player/usePlayer.ts` saves, keys, Media Session | tested (e2e `persist.spec.ts`, `keys.spec.ts`); pagehide keepalive and Media Session: unverified |
| `player/mediaSession.ts` | implemented (no browser run, no device run) |
| `api/Dockerfile`, `docker-compose.yml`, `.dockerignore` | unverified (no container runtime) |
| `api/tests/soak_util.py`, `test_soak_300.py` | fixture; green (525) |
| `api/scripts/sample_sentences.py` | script (output `_agent/results/497_number_forms/`) |

## Code flows

Each flow is a numbered list of steps; each step names **file → function**. `engine` and `state` mean
what they mean in `docs/CODE_MAP_M3.md` (the `PlayerEngine` and the reducer state). Paths under
`api/hearnarro/` are written from `hearnarro/`; paths under `web/src/` from `src/`.

### a. Open the library: `#/` → `GET /documents` with progress (LIB-1)

```
browser        App / Library            client.ts          routes/documents.py         storage/repo.py
  |-- #/ -------->| Library mounts         |                   |                            |
  |               |-- refresh ------------>| getDocuments ---->| list_documents ----------->| list_document_summaries
  |               |                        |                   |   _document_summary per row|  (SUMMARY_SELECT: + segment_count,
  |               |<-- DocumentSummary[] --|<------------------|<---------------------------|     position_order)
  |<-- table: title, pages, progress %, last opened, status, Delete
```

1. **Route.** `src/App.tsx` → `App`: no `#/doc/{id}` match renders `<Library/>`
   (`src/components/Library.tsx`; `Picker.tsx` is deleted).
2. **Load.** `Library` → `refresh(signal)` → `src/api/client.ts` → `getDocuments`. Rows still
   `uploaded`/`parsing` are added to the `polling` list (flow b step 3).
3. **Server.** `hearnarro/routes/documents.py` → `list_documents` → `hearnarro/storage/repo.py` →
   `list_document_summaries`: `SUMMARY_SELECT` adds two subqueries to `DOCUMENT_COLUMNS`,
   `segment_count` and `position_order` (the `order` of `position_segment_id`, only when it belongs to
   the same document). `_document_summary(doc)` builds the one summary shape used by `GET /documents`,
   `GET /documents/{id}` and `PATCH`: the M3 columns plus `segment_count`, `position`
   `{segment_id, offset_ms}` (`{null, 0}` when unset), `progress = position_order / segment_count`
   (0 without a position) and `settings {voice_id, speed}`.
4. **Render.** `Library` → `Row` per document: title links to `#/doc/{id}` only when `status ==
   'ready'`; progress through `src/components/libraryFormat.ts` → `formatProgress` (whole percent,
   floored, clamped); last opened through `formatLastOpened(iso, now)` ("just now", "N min ago", …,
   ISO date after a week, "never"); status shows `parsing pages_done/page_count` while parsing.
5. **Defaults.** `Library` → `Defaults`: `getSettings` and `getVoices`; voice select and speed input
   call `save`, which debounces `putSettings` by 500 ms. Server: `hearnarro/routes/settings.py` →
   `get_settings` / `put_settings` → `_read` over `repo.get_settings` / `repo.put_settings` (key/value
   table; `default_speed` 1.25 when unset, `GlobalSettings` validates [0.5, 3.0]; a null voice deletes
   the key). The defaults never touch a document's own settings (LIB-3).

### b. Upload and poll (LIB-1, ING-1)

1. **Pick.** `Library` → `onUpload`: `<input type="file">` → `client.ts` → `uploadDocument(file)`
   (multipart field `file`, no explicit `Content-Type`; the 15 s request timeout applies).
2. **Server.** `routes/documents.py` → `upload_document` (unchanged from M1): 202 `{id, status:
   'parsing'}` or 200 for known bytes; the parse runs in the process pool (`storage/jobs.py` →
   `run_ingestion`, flows i–k).
3. **Poll.** `Library` → `refresh()` then adds the id to `polling`; an effect runs `setInterval(…,
   POLL_MS = 2000)` that calls `getDocument(id)` for every polled id, merges the result into the row,
   and drops the id once `status` is `ready` or `failed`.

### c. Open a document: `#/doc/{id}` (LIB-2, LIB-3, PLAY-8)

```
DocView                          client.ts                         reducer (machine.ts)
  |-- getDocument, getAllSegments, getVoices, getSettings (.catch -> null) -->|
  |-- LOAD{voice, speed}  ------------------------------------------------>  skip=NO_SKIP, pendingSave=null
  |-- SET_SKIP{skip, skippedIds}   (only if localStorage has toggles on)  ->  current moved off a skipped id
  |-- RESTORE_POSITION{segmentId, offsetMs} (position set and known)      ->  idle only; current = landing
  |-- setLoaded; patchDocument({opened: true}) ----> PATCH /documents/{id} -> last_opened_at = now_iso_ms()
  |-- effect: revealSegment(restoreId) -> engine.scrollTo(id, 'navigate')
```

1. **Load.** `src/App.tsx` → `DocView` effect: `Promise.all([getDocument, getAllSegments,
   getVoices, getSettings])`; a failed `getSettings` becomes `null`, not an error.
2. **Settings precedence (LIB-3).** voice = `doc.settings.voice_id` → global `default_voice_id`
   (only if it is in `/voices`) → first voice → `''`. speed = `doc.settings.speed` → global
   `default_speed` → `DEFAULT_SPEED` (1.25, `src/player/machine.ts`). Dispatched in `LOAD`, which no
   longer carries `position`.
3. **Skip toggles (PLAY-8).** `readSkip(documentId)` reads `localStorage['hearnarro.skip.{id}']`
   inside try/catch; if any toggle is on, `SET_SKIP{skip, skippedIds: skippedIds(segments, skip)}`
   (`src/player/skip.ts`).
4. **Position (LIB-2).** If `doc.position.segment_id != null` and the id is in the segments:
   `RESTORE_POSITION{segmentId, offsetMs}`. `machine.ts` → `reduce` case `RESTORE_POSITION` (idle
   only; id must be in `orderedIds`) sets `current` to `landing(state, pos)`: the position, or the
   next unskipped segment at offset 0 if it is skipped. The first Play (`PLAY` without a segment) then
   starts at `current` with its `offsetMs` (flow b of CODE_MAP_M3).
5. **Opened.** `patchDocument(id, {opened: true})`, errors ignored. Server: `patch_document` →
   `repo.update_document_fields(…, {last_opened_at: repo.now_iso_ms()})`.
6. **Scroll.** `DocView` effect after render → `player.revealSegment(restoreId)` →
   `engine.scrollTo(id, 'navigate')` (centres the segment, keeps follow mode).
7. **Media Session title.** `usePlayer({title})` → `setMediaMetadata(title)` once the title is known
   (flow g).

### d. Position save: tick, pause, pagehide (LIB-2, D26)

1. **Tick.** `src/player/usePlayer.ts` → `usePlayer`: while the rAF loop runs (`looping`),
   `setInterval(dispatch TICK_SAVE, SAVE_TICK_MS = 5000)`. `machine.ts` → case `TICK_SAVE` (only in
   `playing`) sets `pendingSave = {segment_id, offset_ms}` from `current`, a new object every tick.
   `current.offsetMs` is kept fresh by the M3 `POSITION` event (every 250 ms).
2. **Send.** An effect on `state.pendingSave` → `PositionSaver.send(docId, pos)`: at most one PATCH in
   flight; a save asked for during one replaces the queued value and goes out when it settles; an
   identical `docId:segment:offset` key to the last sent save is dropped; a failure clears `last` so
   the next tick retries; nothing is shown to the user. Wire: `client.ts` → `patchDocument(id,
   {position})` → `PATCH /documents/{id}` → `patch_document`: `repo.segment_belongs` (422 if not this
   document's), then `repo.update_document_fields(position_segment_id, position_offset_ms)`.
3. **Pause.** Every pause path (button, Space, Media Session) goes through `pauseAndSave`: `pause()`
   (`ctx.suspend()` + `PAUSE`) then `saver.send(current)` at once.
4. **pagehide (D26).** A `window` `pagehide` listener → `flushSettings(true)` (a waiting settings
   PATCH goes out with keepalive) and, only if a position save already went out in this visit
   (`saver.last !== ''`), `PositionSaver.sendBeacon` → `patchDocument(…, {keepalive: true})` unless
   the value equals the last one sent. `navigator.sendBeacon` is not used.

### e. Settings change in the reader (LIB-3)

1. **Input.** `PlayerBar` voice select / speed slider (or the `+`/`-` keys, flow g) →
   `player.dispatch`, which is `appDispatch` in `usePlayer.ts`.
2. **Reducer.** `SET_VOICE` / `SET_SPEED`: as in M3 for `playing` and `paused|idle`; new in M4, in
   `loading` the value is kept and `generation` is bumped (`load(state, 'loading', current)`), so the
   in-flight load goes stale and the build effect rebuilds at the new key.
3. **Save.** `appDispatch` restarts a 500 ms timer (`SETTINGS_DEBOUNCE_MS`); when it fires,
   `sendSettings(false)` → `patchDocument(id, {settings: {voice_id, speed}})` with both fields from the
   current state. Server: `patch_document` validates `speed` in [0.5, 3.0] (`DocSettingsIn`) and
   writes only the keys present (`model_fields_set`); `settings: null` clears both.
4. **Unmount / pagehide.** The pagehide effect's cleanup calls `flushSettings(false)`; pagehide calls
   `flushSettings(true)`.

### f. Delete (LIB-4)

1. **Confirm.** `Library` → `Row`: "Delete" → inline "Confirm delete" / "Cancel"; confirm →
   `onDelete(id)` → `client.ts` → `deleteDocument(id)` (`DELETE`, resolves on 204, throws `ApiError`
   otherwise; the row shows the error).
2. **Server.** `routes/documents.py` → `delete_document`: `_summary_or_404`; 409 when `status ==
   'parsing'`; `repo.delete_document` deletes `audio_cache` (via the document's segments), `segments`,
   `sections`, `blocks`, `documents` in one transaction; then, off the event loop, unlinks
   `pdfs/{sha256}.pdf` and removes `audio/{id}/`. 204.
3. **UI.** The row and its poll entry are removed locally; no refetch.

### g. Keyboard and Media Session to one dispatch (PLAY-6, PLAY-7)

```
keydown (document) --> keys.keyToAction --> TOGGLE -> play() | pauseAndSave()
                                         \-> SKIP / SKIP_SECTION -> appDispatch
                                          \-> SPEED{delta} -> appDispatch(SET_SPEED{stepSpeed(speed, delta)})
mediaSession action --> setMediaHandlers: play -> play(); pause -> pauseAndSave();
                                          previoustrack / nexttrack -> appDispatch(SKIP{-1|+1})
```

1. **Listener.** `usePlayer.ts` → one `document` `keydown` listener; modified keys (Ctrl/Meta/Alt)
   are ignored. `src/player/keys.ts` → `keyToAction({key, shiftKey, target})` returns null for an
   editable target (input, select, textarea, contenteditable) or an unmapped key. Space → `TOGGLE`;
   `←`/`→` → `SKIP{∓1}`; `Shift+←/→` → `SKIP_SECTION{∓1}`; `+`/`=` → `SPEED{+0.25}`; `-` →
   `SPEED{-0.25}`.
2. **Dispatch.** `TOGGLE` is ignored on a focused `BUTTON` or `A`; otherwise `preventDefault()` and
   `pauseAndSave()` when playing, else `play()`. Other actions `preventDefault()` and go through
   `appDispatch`; `SPEED` uses `stepSpeed` (0.05 grid, clamped to [0.5, 3.0]), so a key speed change
   also triggers the settings save (flow e).
3. **Follow mode.** The M3 scroll-key listener now returns early on `e.defaultPrevented`, so Space and
   the arrows no longer turn follow mode off.
4. **Media Session.** `src/player/mediaSession.ts`: `setMediaHandlers({play, pause, previoustrack,
   nexttrack})` installs the four handlers (each in try/catch) and returns a cleanup;
   `setMediaPlaybackState(status)` mirrors the machine (`playing|loading` → `playing`, `paused` →
   `paused`, else `none`); `setMediaMetadata(title)` sets title and artist "HearNarro";
   `clearMediaSession()` runs on unmount. Every call is a no-op where `navigator.mediaSession` is
   missing.

### h. Skip toggles to the schedule (PLAY-8)

1. **Toggle.** `PlayerBar` renders three checkboxes from `state.skip` (`Skip footnotes`, `Skip
   captions`, `Skip references`) → `onSkipChange(newSkip)` → `DocView` → `writeSkip` (localStorage,
   try/catch) and `SET_SKIP{skip, skippedIds: skippedIds(segments, skip)}`.
2. **Rules.** `src/player/skip.ts` → `skippedIds`: `isSkipped` per segment; footnotes = `type ==
   'footnote'`, captions = `type == 'caption'`, references = `referenceIds(segments)`: every segment
   from a heading matching `REFERENCES_HEADING` (`/^(references|bibliography|works cited)\b/i`) up to
   the next heading.
3. **Reducer.** case `SET_SKIP` stores both; in `playing|loading` it rebuilds from
   `landing(next, current)` (generation + 1) so already scheduled skipped clips are dropped; in
   `idle|paused` it only moves `current` off a skipped id. `PLAY` with a segment, `SEEK`, `SKIP`
   (direction of travel), `SKIP_SECTION` and `RESTORE_POSITION` all land on the next unskipped id via
   `nextUnskipped` / `unskipped`.
4. **Schedule.** `usePlayer.ts` → `PlayerEngine.ensureWindow` builds the prefetch span from the target
   plus the next `PREFETCH_DEPTH` ids not in `state.skippedIds` (skipped ids are never fetched);
   `scheduleReady` and `tick` call `nextPlayable(orderedIds, tail, engine.blocked())`, where
   `blocked()` is the user's skips plus the M3 failed-prefetch set.
5. **Render.** `src/components/Reader.tsx` → `SegmentView` adds the `skipped` class (dimmed in
   `styles/app.css`) for ids in the `skipped` set passed from `DocView`.

### i. Ingestion with OCR fallback (ING-2, D28)

```
storage/jobs.run_ingestion -> pipeline.ingest(pdf, ocr_backend=DEFAULT_OCR)
   backend = default_backend()  (TesseractBackend if `tesseract` on PATH, else None)
   extract.extract_pages(pdf, ocr=False)   -> pages, each with page.text_chars
   ocr.apply_ocr(pdf, pages, backend)      -> per page:
        text_chars >= 20 ? keep
        ink_coverage(render_page(100 dpi, gray)) ; needs_ocr(chars, ink) ? (chars < 20 and ink > 0.5 %)
           no  -> keep
           yes -> page emptied; backend None -> skipped += 1 (left empty, logged)
                  else drop scan-sized image/figure boxes; render 300 dpi RGB;
                       lines_to_blocks(backend.recognize(image))   (blocks ocr=True)
   classify -> order -> merge -> split_sentences ; IngestResult.ocr_skipped_pages = skipped
jobs._write_result -> UPDATE documents SET ..., ocr_skipped_pages = ?
```

1. **Stage 1.** `hearnarro/ingestion/extract.py` → `page_from_layout` sets `Page.text_chars =
   _char_count(page)` (non-space glyphs). `extract_pages` empties a page under `min_text_chars` (20)
   as before, but no longer calls the legacy `ocr_page` in the loop; with `ocr=True` it ends by
   resolving `ocr_backend` and running `apply_ocr` (lazy import from `ocr.py`).
2. **Pipeline.** `hearnarro/ingestion/pipeline.py` → `ingest(…, ocr_backend=DEFAULT_OCR)`: resolves
   the sentinel with `default_backend()`, calls `extract_pages(ocr=False)` and then `apply_ocr` itself
   when `ocr` is true, so OCR runs once per ingest.
3. **Decision.** `hearnarro/ingestion/ocr.py` → `apply_ocr`: `page_text_chars(page)`; pages at or
   above `MIN_TEXT_CHARS` are skipped without rendering; otherwise `render_page(pdf, n, INK_DPI=100,
   grayscale=True)` → `ink_coverage` (share of pixels under `INK_LEVEL=128`) → `needs_ocr(chars, ink)`
   (`ink > MIN_INK = 0.005`). A blank page is never sent.
4. **No engine.** `backend is None`: the page stays empty (`has_text_layer = False`, no blocks),
   `skipped += 1`, and one `log.info` line names the count and the file.
5. **Engine.** Image and figure boxes covering more than `SCAN_AREA` (50 %) of the page are dropped
   (`_is_scan`), the page is rendered at `OCR_DPI=300` RGB with `image.info["dpi"]`, and
   `backend.recognize(image)` returns `OcrLine{text, bbox}` in PDF points. `lines_to_blocks` sorts
   lines top-to-bottom, starts a block at a gap above `LINE_GAP` (1.5) line heights, marks blocks
   `ocr=True`. `TesseractBackend.recognize` runs `tesseract page.png stdout --psm 3 tsv` and
   `parse_tsv` groups level-5 word rows by (block, par, line), scaling pixels by `72/dpi`.
   `FakeOCRBackend` returns fixture lines and records each image (tests).
6. **Persist.** `IngestResult.ocr_skipped_pages` → `storage/jobs.py` → `_write_result` writes
   `documents.ocr_skipped_pages` (column from migration `0004_ocr_skipped_pages.py`; NULL for rows
   ingested before it). The value is not yet part of the API summary (`repo.DOCUMENT_COLUMNS`).

### j. Sections at ingestion (ING-8, D25)

1. **Write.** `storage/jobs.py` → `_write_result`: deletes the document's old `segments`, `sections`,
   `blocks` (re-ingest safe); `heading_text = {block.id: text}` for heading blocks; walks segments in
   `order`; the first segment of each heading block inserts a `sections` row (`level = 1`,
   `first_segment_id` NULL), then the segment is inserted with the current `section_id` (NULL before
   the first heading), then `UPDATE sections SET first_segment_id`. Segments are inserted one by one
   (not `executemany`) so each gets its id.
2. **Read.** `routes/documents.py` → `get_document` returns `repo.list_sections` (non-empty for new
   uploads). `src/components/Reader.tsx` → `deriveSections` prefers them; documents ingested before
   this change keep empty `sections` and the client still derives them (D25). `hearnarro renormalize`
   does not rebuild sections.

### k. Table and equation cues, page markers, ligatures (ING-7, ING-4, ING-5)

1. **Page markers (ING-4).** `hearnarro/ingestion/classify.py` → `_classify`: a block matching
   `PAGE_MARKER_RE` (`[47]` or a bare 1–4 digit number, except a bare 19xx/20xx year) that overlaps no
   table is `noise`, checked after the table rule and before the heading rule.
2. **Ligatures (ING-5).** `extract.py` → `_line_from_layout` translates each glyph through
   `LIGATURE_CHARS` (U+FB00–U+FB06 → ff, fi, fl, ffi, ffl, st, st); `_LIGATURE_UNI` gains FB05/FB06.
3. **Heading hyphen (ING-4).** `hearnarro/ingestion/merge.py` → `merge_lines(lines, heading=True)`
   keeps a line-final hyphen and joins with no space ("Multi-" + "Modal" → "Multi-Modal");
   `merge_blocks` passes `heading=block.type == 'heading'`.
4. **Tables (ING-7).** `merge_blocks` → `_table_groups(blocks)` numbers tables through the document;
   consecutive same-page table blocks are one table whose row counts add up. For each table block,
   `table_rows(block)` → per line `table_cells(line)` (spans split where the gap exceeds `CELL_GAP` = 1
   font size; spans closer than `WORD_GAP` join without a space) joined with ", " and ended with ".";
   rows without a letter and noise lines are dropped. The first block of a table gets the cue
   `Table N, R rows.` (`1 row.` when one). The `LogicalBlock.text` is the cue and rows joined by
   newlines; `raw_text` keeps the merged raw text for the D14 excluded-mass guard
   (`api/tests/golden_util.py` → `excluded_actual_texts`).
5. **Equations (ING-7).** `merge_blocks` → `equation_cue(lines)`: `Equation N.` when a line ends with
   a label like `(3)` (`EQUATION_LABEL_RE`), else `Equation.`; `raw_text` keeps the symbols. Inline
   equation fragments (stage 3 `inline`) still join their host sentence as before.
6. **Segments.** `hearnarro/ingestion/segment.py` → `split_sentences`: for `table` and `equation`
   blocks `_line_spans(text)` makes one segment per non-empty line instead of pySBD.

### l. `hearnarro purge-audio` (D19 tooling)

1. **CLI.** `hearnarro/cli.py` → `main`: subcommand `purge-audio --document-id N [--data-dir D]
   [--segment-id S] [--voice V] [--speed X]` → `_purge_audio` → `resolve_data_dir`, `connect_sync`.
2. **Delete.** `purge_audio(conn, data_dir, document_id, *, segment_id, voice, speed)`: one `WHERE`
   clause (segments of the document, plus optional `segment_id`, `voice_id`, `abs(speed - ?) <
   SPEED_EPSILON`), selects the `path`s, deletes the rows in one transaction, then unlinks the files.
   Prints `audio cache entries removed: N`; empty directories stay.

### m. Static serving (D21)

1. **Resolve.** `hearnarro/settings.py` → `web_dist_dir(env)`: `$HEARNARRO_WEB_DIST`, else
   `<repo>/web/dist` (`REPO_ROOT`); None when the directory does not exist.
2. **Mount.** `hearnarro/app.py` → `create_app`: after the `documents`, `audio`, `voices` and
   `settings` routers, `app.mount("/", StaticFiles(directory=dist, html=True), name="web")` when a dist
   exists, so API paths keep winning. Without it `/` is 404 and the API still serves. No SPA fallback
   is needed (hash routes).
3. **Dev.** `web/vite.config.ts` proxies `/settings` too, next to `/documents`, `/audio`, `/voices`.

### n. Docker image build and run (D30)

1. **Build.** `docker-compose.yml` → one service `api` built from `api/Dockerfile` with the repo root
   as context (`.dockerignore` drops `.git`, venvs, `node_modules`, tests, `web/dist`, `data`,
   `_agent`, `docs`, key files).
2. **Stage `web`.** `node:24-slim`: `npm ci --ignore-scripts`, `npm run build` → `/src/web/dist`.
3. **Stage `runtime`.** `python:3.11-slim`; `ARG KOKORO_REVISION` (the D15 pin); env
   `HEARNARRO_DATA_DIR=/data`, `HEARNARRO_WEB_DIST=/app/web/dist`, `HEARNARRO_TTS_BACKEND=kokoro`,
   `HF_HOME=/hf_home`; `pip install --extra-index-url …/whl/cpu -e ".[tts]"` (editable, CPU torch);
   copies `web/dist`; volumes `/data`, `/hf_home`; port 8765; `HEALTHCHECK` GETs `/documents`.
4. **Run.** `CMD python -m hearnarro serve --data-dir /data --host 0.0.0.0 --port 8765`; Compose maps
   `8765:8765`, binds `./data:/data`, names volume `hf_home`, sets `HEARNARRO_AUDIO_FORMAT=wav`,
   `restart: unless-stopped`. The app then serves the API and, through flow m, the web app at `/`.
   Steps for the user: `docs/DOCKER.md`. Not run here (no runtime): **unverified**.

## Modules and files

### `api/hearnarro/`

| File | Responsibility | Public (M4 additions) | Reads / writes | Status |
| --- | --- | --- | --- | --- |
| `routes/documents.py` | Summary shape for list/detail/PATCH; PATCH position/settings/opened; DELETE with files | `list_documents`, `get_document`, `patch_document`, `delete_document`, `DocumentPatch`, `PositionIn`, `DocSettingsIn`, `SPEED_MIN`, `SPEED_MAX`; internal `_document_summary`, `_summary_or_404` | `documents`, `segments`, `sections`; `pdfs/`, `audio/{id}/` | tested (503, 525) |
| `routes/settings.py` (new) | Global defaults over the key/value table | `router`, `get_settings`, `put_settings`, `GlobalSettings`, `DEFAULT_SPEED` (1.25) | `settings` table | tested (503) |
| `app.py` | Includes the settings router; mounts `web/dist` after the routers (D21) | `create_app` | dist directory | tested (`test_static_web.py`) |
| `settings.py` | `HEARNARRO_WEB_DIST`, repo root, dist resolution | `web_dist_dir`, `WEB_DIST_ENV`, `REPO_ROOT` | env, filesystem | tested |
| `cli.py` | `purge-audio` subcommand | `purge_audio`, `main`; `SPEED_EPSILON` | `audio_cache`; files under the data dir | tested (`test_purge_cli.py`) |
| `storage/repo.py` | Summary select, membership check, field update, cascade delete, settings get/put, ms timestamps | `SUMMARY_SELECT`, `list_document_summaries`, `get_document_summary`, `segment_belongs`, `update_document_fields`, `delete_document`, `get_settings`, `put_settings`, `now_iso_ms` | `documents`, `segments`, `sections`, `blocks`, `audio_cache`, `settings` | tested |
| `storage/jobs.py` | Writes sections + `section_id` (ING-8) and `ocr_skipped_pages` (ING-2) | `run_ingestion`; internal `_write_result` | `sections`, `segments`, `blocks`, `documents` | tested (506, 538) |
| `storage/migrations/versions/0004_ocr_skipped_pages.py` (new) | `ALTER TABLE documents ADD COLUMN ocr_skipped_pages INTEGER`; downgrade drops it | `upgrade`, `downgrade` | schema | tested (538) |
| `ingestion/ocr.py` (new) | OCR decision and backends (D28) | `OcrLine`, `OCRBackend`, `FakeOCRBackend`, `TesseractBackend`, `parse_tsv`, `DEFAULT_OCR`, `default_backend`, `ink_coverage`, `needs_ocr`, `page_text_chars`, `render_page`, `lines_to_blocks`, `apply_ocr`; constants `MIN_TEXT_CHARS`, `MIN_INK`, `INK_LEVEL`, `INK_DPI`, `OCR_DPI`, `LINE_GAP`, `SCAN_AREA` | PDF via pypdfium2; `tesseract` subprocess | tested with the fake (547); Tesseract unverified |
| `ingestion/extract.py` | `Page.text_chars`; FB00–FB06 ligatures; `ocr_backend` keyword, legacy `ocr_page` no longer called | `extract_pages`, `page_from_layout`, `LIGATURE_CHARS` | PDF | tested |
| `ingestion/classify.py` | Page-marker blocks → noise | `PAGE_MARKER_RE`, `classify_pages` | none | tested (534) |
| `ingestion/merge.py` | Heading hyphen join; table rows and cue; equation cue; `raw_text` | `merge_lines`, `table_cells`, `table_rows`, `equation_cue`, `merge_blocks`, `CELL_GAP`, `WORD_GAP`, `EQUATION_LABEL_RE`; internal `_table_groups`, `_logical` | none | tested (534, 535) |
| `ingestion/segment.py` | One segment per line for table/equation blocks | `split_sentences`; internal `_line_spans` | none | tested |
| `ingestion/models.py` | `Page.text_chars`, `LogicalBlock.raw_text` | dataclasses | none | tested |
| `ingestion/pipeline.py` | Resolves the OCR backend, runs `apply_ocr` between stage 1 and classify | `ingest`, `IngestResult.ocr_skipped_pages` | none | tested |

### `api/` tests, scripts, packaging

| File | Responsibility | Requirement | Status |
| --- | --- | --- | --- |
| `tests/test_lib_gate.py`, `test_static_web.py`, `test_purge_cli.py` | Phase 1 server gate | LIB-1..4, D21, D19 | green (503) |
| `tests/test_ing8_sections.py` | Sections rows and `section_id` | ING-8 | green (506) |
| `tests/test_ing2_ocr.py` | Detection on `scanned_0N`, blank and text pages; fake and (marked `ocr`) real engine | ING-2 | green (547; tesseract test skipped) |
| `tests/test_ing4_page_markers.py`, `test_ing7_tables.py`; edits in `test_ing4_merge.py`, `test_ing4_reading_order_golden.py`, `golden_util.py` | Phase 3 rules; D14 guard reads `raw_text` | ING-4, ING-5, ING-7, D14 | green (534, 535, 548) |
| `tests/soak_util.py` | `generate_soak_pdf(path, pages=300, seed=300)`: seeded reportlab PDF, ~20 varied sentences per page, a "Chapter N" heading every tenth page | gate 1 | fixture |
| `tests/test_soak_300.py` | `test_soak_300_pages_ingest_page_audio_delete` (`@pytest.mark.soak`): ready < 300 s, RSS < 1536 MB, paging in order, `/audio` first/last, delete clean; prints a `SOAK` line | gate 1 | green (525) |
| `tests/conftest.py`, `pyproject.toml` | `soak`/`ocr` markers; `reportlab==4.4.10` dev dependency | harness | fixture |
| `scripts/sample_sentences.py` | `main(argv)`: normalizes `SENTENCES` (spec §3a) or given sentences, synthesizes each with `make_backend('kokoro'|'fake')` to `NN.wav`, writes `index.md` | ING-6 by ear | script |
| `Dockerfile` (new) | Two-stage image: web build, Python runtime serving both | D30, D21 | unverified |

### Repo root

| File | Responsibility | Status |
| --- | --- | --- |
| `docker-compose.yml` | One service `api` (the `web` service removed), port 8765, `./data` bind, `hf_home` volume | unverified (YAML checked, 528) |
| `.dockerignore` (new) | Keeps local state, tests, `_agent`, docs and keys out of the build context | checked (530) |
| `docs/DOCKER.md` (new) | User steps for gate clause 3 | doc |

### `web/src/`

| File | Responsibility | Public (M4 additions) | Reads / writes | Status |
| --- | --- | --- | --- | --- |
| `App.tsx` | Routes `#/` to `Library`; `DocView` loads globals, applies settings precedence, `SET_SKIP` from localStorage, `RESTORE_POSITION`, `opened`, reveal; skip toggles callback | `default App`; internal `DocView`, `readSkip`, `writeSkip` | client; `localStorage['hearnarro.skip.{id}']` | tested (e2e) |
| `components/Library.tsx` (new; replaces `Picker.tsx`) | Documents table, upload + 2 s polling, delete with inline confirm, global defaults | `Library`, `POLL_MS`; internal `Row`, `Defaults` | `GET/POST/DELETE /documents`, `GET /documents/{id}`, `GET/PUT /settings`, `GET /voices` | tested (e2e `library.spec.ts`, `persist.spec.ts`) |
| `components/libraryFormat.ts` (new) | Progress and last-opened text | `formatProgress`, `formatLastOpened` | none | tested (unit) |
| `components/PlayerBar.tsx` | Three skip checkboxes | `PlayerBar`, `PlayerBarProps.onSkipChange` | `state.skip` | tested (e2e `skip.spec.ts`) |
| `components/Reader.tsx` | `skipped` class on skipped segments | `Reader`, `ReaderProps.skipped`, `deriveSections` | DOM | tested (e2e) |
| `player/keys.ts` (new) | Pure key map | `keyToAction`, `stepSpeed`, `KeyAction`, `KeyInput`, `SPEED_MIN`, `SPEED_MAX`, `SPEED_STEP` | event tag name only | tested (unit `keys.test.ts`, e2e `keys.spec.ts`) |
| `player/skip.ts` (new) | Pure skip rules | `SkipState`, `NO_SKIP`, `REFERENCES_HEADING`, `referenceIds`, `isSkipped`, `skippedIds`, `nextUnskipped` | none | tested (unit `skip.test.ts`) |
| `player/mediaSession.ts` (new) | Feature-detected Media Session wrapper | `MediaHandlers`, `setMediaMetadata`, `setMediaHandlers`, `setMediaPlaybackState`, `clearMediaSession` | `navigator.mediaSession` | implemented (no run) |
| `player/machine.ts` | Adds `skip`, `skippedIds`, `pendingSave`; events `SET_SKIP`, `RESTORE_POSITION`, `TICK_SAVE`; skipped-aware landing; settings kept in `loading` | `reduce`, `initialState`, `DEFAULT_SPEED`, `PlayerEvent`, `PlayerContext`; internal `landing`, `unskipped` | none | tested (unit `machine.test.ts`) |
| `player/usePlayer.ts` | Save tick, `PositionSaver`, pause save, pagehide flush, settings debounce, keydown map, Media Session, skip-aware prefetch and chaining, `revealSegment` | `usePlayer(opts)`, `PositionSaver`, `SAVE_TICK_MS`, `SETTINGS_DEBOUNCE_MS`, `Player.revealSegment`, `PlayerEngine.blocked` | `PATCH /documents/{id}`; `document` keydown; `window` pagehide | tested (e2e); pagehide keepalive unverified |
| `api/client.ts` | JSON writes and upload through the same `request()` (15 s timeout) | `patchDocument`, `deleteDocument`, `getSettings`, `putSettings`, `uploadDocument`; internal `sendJson` | HTTP | tested (unit `client.test.ts`) |
| `api/types.ts` | Summary gains `segment_count`, `position`, `progress`, `settings`, `last_opened_at`; `DocumentDetail` extends it | `DocumentSummary`, `DocumentDetail`, `DocumentPatch`, `GlobalSettings`, `UploadResult`, `DocumentPosition`, `DocumentSettings` | none | tested (typecheck 515) |
| `styles/app.css` | Library table, defaults, skip toggles, `.seg.skipped` dimming | n/a | n/a | implemented |

### `web/tests/` and config

| File | Responsibility | Requirement | Status |
| --- | --- | --- | --- |
| `unit/keys.test.ts`, `skip.test.ts`, `library.test.ts`; additions to `machine.test.ts`, `client.test.ts` | Key map; skip rules incl. references span; formatting; new events; new client calls | PLAY-6, PLAY-8, LIB-1..3 | green (514) |
| `e2e/library.spec.ts`, `persist.spec.ts`, `keys.spec.ts`, `skip.spec.ts` | LIB-1/4 in the page; LIB-2/3 across a reload; PLAY-6; PLAY-8 | as listed | green (519, 544, 545) |
| `e2e/soak.spec.ts` | Gate clause 2 on the 300-page document | gate 2, LIB-2, PLAY-2, D29 | green (542) |
| `e2e/fixtures.ts` | Extended harness (eadaef6) | harness | fixture |
| `vite.config.ts` | Proxies `/settings` | D21 | tested |

## Data structures

**Document summary** (`routes/documents.py` → `_document_summary`; `src/api/types.ts` →
`DocumentSummary`): `id, title, filename, sha256, page_count, pages_done, parse_ms, status,
fail_reason, created_at, last_opened_at, segment_count, position {segment_id | null, offset_ms},
progress, settings {voice_id, speed}`. `GET /documents/{id}` adds `sections` and `acronyms`.

**PATCH body** (`DocumentPatch`): `position {segment_id, offset_ms ≥ 0} | null`, `settings
{voice_id?, speed? ∈ [0.5, 3.0]} | null`, `opened: true`. Absent keys are untouched; `null` clears.

**`PlayerContext` additions** (`machine.ts`): `skip: SkipState`, `skippedIds: number[]`,
`pendingSave: {segment_id, offset_ms} | null`.

**`PositionSaver`** (`usePlayer.ts`): `inFlight`, `queued`, `last` (`docId:segment:offset`).

**`OcrLine`** (`ocr.py`): `{text, bbox}` in PDF points, origin top-left.

**Schema**: `documents.ocr_skipped_pages INTEGER` (0004); `sections` rows and `segments.section_id`
now populated by ingestion; `settings` keys `default_voice_id`, `default_speed`.

## Spec deviations

What the code does where it departs from `_agent/specs/m4-library-interfaces.md`. Numbered
consecutively; the source report and its own number are in brackets.

**Server (phase 1)**

1. PATCH also validates per-document `settings.speed` in [0.5, 3.0] (422); the spec states the bound
   only for `PUT /settings`. [`m4-1-build-lib` 1]
2. PATCH `position.offset_ms` defaults to 0 and must be ≥ 0; `settings.voice_id` is not checked
   against `/voices`. [`m4-1-build-lib` 2]
3. An unset position is `{segment_id: null, offset_ms: 0}`, never `null`. [`m4-1-build-lib` 3]
4. `last_opened_at` is written with millisecond precision (`repo.now_iso_ms`); `created_at` keeps
   seconds. [`m4-1-build-lib` 4]
5. `purge-audio` needs `--data-dir` (or `$HEARNARRO_DATA_DIR`); `--speed` matches within 1e-6; it
   prints `audio cache entries removed: N`; empty audio directories stay on disk.
   [`m4-1-build-lib` 5]
6. DELETE returns 409 only for status `parsing` (an `uploaded` row can be deleted).
   [`m4-1-build-lib` 6]
7. ING-8: a heading block with no segments gets no section row; re-ingest deletes the document's old
   sections first; segments are inserted one at a time instead of `executemany`.
   [`m4-1-build-ing8` ASSUMED and OBSERVATIONS]

**Client core (phase 2)**

8. Settings during `loading` are applied by a generation bump (rebuild), not a deferred
   `pendingSettings` field. [`m4-2-build-core` 1]
9. `DocumentDetail` inherits `position`/`settings` from `DocumentSummary`; the summary gains
   `segment_count`, `position`, `progress`, `settings`, `last_opened_at`. `DocumentPosition.segment_id`
   stays typed `number` although the wire can send null. [`m4-2-build-core` 2 and ASSUMED 2]
10. `LOAD` resets `skip` to `NO_SKIP`, `skippedIds` to `[]` and `pendingSave` to null.
    [`m4-2-build-core` 3]
11. `PLAY` with a `segmentId`, `SKIP_SECTION` and `RESTORE_POSITION` also land on the next unskipped
    segment. [`m4-2-build-core` 4]

**Client UI (phase 2)**

12. Space is ignored by the shortcut when the target is a `BUTTON` or `A` (the focused control already
    turns Space into a click). Done in `usePlayer`, `keys.ts` unchanged. [`m4-2-build-ui` 1]
13. Space and arrow shortcuts call `preventDefault`; the follow-mode scroll-key listener skips
    `defaultPrevented` events, so the Space shortcut does not turn follow mode off. [`m4-2-build-ui` 2]
14. The `pagehide` keepalive PATCH is sent only after a position save already went out in this visit
    and only if the value changed; a debounced settings PATCH waiting at `pagehide` is flushed with
    keepalive too. [`m4-2-build-ui` 3]
15. The library polls `GET /documents/{id}` every 2 s for every row not ready/failed (also rows found
    parsing on load), not only the uploaded one. [`m4-2-build-ui` 4]
16. The reader settings PATCH sends both fields, `{voice_id, speed}`, from the current state.
    [`m4-2-build-ui` 5]
17. The UI worker changed no pure module (`machine.ts`, `keys.ts`, `skip.ts`, `client.ts`,
    `types.ts`); skip wiring (localStorage, `SET_SKIP`) lives in `App.tsx` `DocView`, not in
    `usePlayer`. A "Last opened" column was added. [`m4-2-build-ui` 6, ASSUMED, OBSERVATIONS]

**Ingestion rules (phase 3)**

18. Page-marker regex: a bare 19xx/20xx is not a marker (a lone year stays content;
    `test_ing2_classify` expects a mid-page "2024" to stay body). [`m4-3-build-rules` 1]
19. A table cell break needs a horizontal gap of more than 1 font size between spans.
    [`m4-3-build-rules` 2]
20. The golden test file was edited to apply D14 through `LogicalBlock.raw_text`
    (`golden_util.excluded_actual_texts`). [`m4-3-build-rules` 3]
21. "R rows" counts spoken rows (rows with no letters skipped), one row is `1 row.`; back-to-back
    table blocks on one page are one table with the cue on the first block only; inline equation
    fragments still join their host sentence as raw text. [`m4-3-build-rules` ASSUMED]

**OCR (phase 3)**

22. The `ocr_backend` keyword was first on `ingest()` only; `ingest` calls `extract_pages(ocr=False)`
    then `ocr.apply_ocr(pdf, pages, backend)`. The old pytesseract `ocr_page` path is no longer used.
    [`m4-3-build-ocr` 1]
23. On a page sent to OCR, image/figure boxes covering more than 50 % of the page are dropped;
    otherwise the scan image makes every recognized line D12 "figure" text. [`m4-3-build-ocr` 2]
24. `page_text_chars()` reads `getattr(page, "text_chars")` and falls back to counting glyphs.
    [`m4-3-build-ocr` 3]
25. No dependency added: pillow was already installed. [`m4-3-build-ocr` 4]
26. `DEFAULT_OCR` / `_Default` moved to `ocr.py`; `extract_pages` gained `ocr_backend` and runs
    `apply_ocr` after the page loop (lazy import); the legacy `ocr_page` call was removed from the loop
    (the function is left in place); two `test_ing4_merge` assertions now expect `Equation.`.
    [`m4-3-wire-ocr`]

**Soak and packaging (phase 4)**

27. The Dockerfile uses `pip install -e ".[tts]"` instead of `pip install .[tts]`, because
    `hearnarro/storage/migrations` has no `__init__.py` and a wheel install would probably drop
    `env.py`/`versions/` (not tested); it also uses the CPU-only PyTorch index.
    [`m4-4-docker` OBSERVATIONS]
28. The server binds `0.0.0.0:8765` through `CMD` flags (the CLI defaults are `127.0.0.1:8000`).
    [`m4-4-docker` OBSERVATIONS]
29. `reportlab` is pinned at 4.4.10 (4.2.5 pulls LGPL `chardet`); the soak test has its own 600 s
    poll deadline instead of `pytest-timeout`. [`m4-4-soak-api` ASSUMED, OBSERVATIONS]

Against the Technical Design: D25's "client derives sections" stays as the fallback for documents
ingested before ING-8. D29 (virtualised rendering) is not built, decided by the soak (first render
619 ms, `_agent/results/542_soak_browser.txt`).

## Dependencies and licences

Python dev: `reportlab==4.4.10` (BSD-3) for the soak fixture; licence check 102 packages, 0
violations (`_agent/results/524_soak_licence.txt`). No new runtime Python dependency; Tesseract is an
optional external binary behind `OCRBackend` (D28). No new npm package.

## How to run

The commands with expected output go in `docs/M4_TESTING.md` (phase 5). Docker: `docs/DOCKER.md`.

## What is left (M5 and follow-ups)

| Item | Where | Lands in |
| --- | --- | --- |
| Gate clause 3: `docker compose up --build`, `GET /documents` 200, web app at `/` (no runtime here; also when Kokoro downloads its model in the container) | `api/Dockerfile`, `docker-compose.yml` | user run, before M4 close |
| `TesseractBackend` against a real binary (none on PATH; test marked `ocr`) | `ingestion/ocr.py` | user installs Tesseract (D28) |
| `ocr_skipped_pages` not exposed in the API summary or the library | `storage/repo.py` `DOCUMENT_COLUMNS`, `Library.tsx` | M5 |
| Media Session on a real browser and phone lock screen (PLAY-7) | `player/mediaSession.ts` | manual check |
| `pagehide` keepalive PATCH has no test | `usePlayer.ts` | follow-up test |
| DELETE does not stop synthesis lookahead already running; a job in flight could recreate a file under `audio/{id}/` | `routes/documents.py`, synthesis queue | M5 |
| `uploadDocument` shares the 15 s request timeout; a large upload may time out | `api/client.ts` | M5 |
| `DocumentPosition.segment_id` typed `number` while the wire can send null | `api/types.ts` | follow-up |
| Documents ingested before M4 keep empty `sections`, page-marker and table/equation text; `renormalize` does not reclassify or rebuild sections (re-upload needed) | `cli.py` `renormalize` | M5 or user re-upload |
| Section `level` is always 1 (classify has no heading rank) | `storage/jobs.py`, `classify.py` | M5 |
| ING-6 number-form rules: only the sampler landed in this range; rules wait for the user's listening verdicts | `ingestion/normalize.py` | M5 |
| D19 clause-chunking A/B (optional): `purge-audio` is ready, the measurement was not run | `cli.py`, `web/scripts/measure_first_audio.mjs` | user's call |
| D16 default format: one play in the user's own Safari | `api` settings | user |
| `purge-audio` leaves empty audio directories | `cli.py` | follow-up |
| PRD "Packaging" still says "API, worker and web" (D30 is one service); D26–D30 into the TD | `docs/PRD.md`, `docs/TECHNICAL_DESIGN.md` | phase 5 docs sync |
| Out of scope for M4: PLAY-9 export, PDF page view, iOS background playback | PRD | M5 / open question |
