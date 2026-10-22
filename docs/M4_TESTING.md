# Testing M4 (library and polish) by hand

About 30 minutes. You build the web app, start your own Kokoro server, which now also serves the app,
check the new API routes with `curl`, then use the library and the reader in a browser: upload,
position restore, remembered settings, keyboard, skip toggles, delete, Media Session. Then you
listen to the twelve number-form clips, run the two soak tests and, on a machine that has Docker,
the container. What you are checking is LIB-1 to LIB-4, PLAY-6 to PLAY-8, the static app (D21), the
`purge-audio` command (D19) and the M4 gate (`docs/PRD.md`, `_agent/specs/m4-library-interfaces.md` §0).

All `npm` commands run from `web/`, all `python` commands from `api/`, all `curl` commands from the
repo root. The doc was followed cold on 2026-10-17 against the live Kokoro server and your own data
directory `~/yomikoe-m1` (19 documents); every output quoted below is in
`_agent/results/551_m4_testing_cold.txt` under the heading named in brackets, e.g. `[S2]`.

## 1. Prerequisites

Everything from `docs/M3_TESTING.md` section 1: `api/.venv` with the `dev` and `tts` extras, Node in
`~/.local/node` (`bash web/scripts/install_node.sh` once), `npm ci` and the Playwright browsers.
Run `source web/scripts/env.sh` (from the repo root) or `source scripts/env.sh` (from `web/`) in every
new shell.

## 2. Build the app and start the server

```bash
cd web && source scripts/env.sh && npm run build && cd ..
# dist/index.html, dist/assets/index-*.css (about 4 kB), index-*.js (about 256 kB, 80 kB gzip)

cd api
HF_HOME=~/yomikoe-m1/hf YOMIKOE_TTS_BACKEND=kokoro \
  .venv/bin/python -m yomikoe serve --data-dir ~/yomikoe-m1 --port 8765
```

The first start on M4 code applies Alembic migration 0004 (`documents.ocr_skipped_pages`) to your
database; that is expected and leaves your documents alone. The model loads in 10–60 s; the server
is ready when `Uvicorn running on http://127.0.0.1:8765` appears and `curl -s
http://127.0.0.1:8765/voices` returns a JSON list (`[S4]`: `af_heart`, `af_bella`, ... ).

The server serves `web/dist` at `/` when that directory exists (`YOMIKOE_WEB_DIST` points it
elsewhere). If you skip the build, the API still works and `/` returns 404.

## 3. The API (curl, second terminal, repo root)

Set two helpers first:

```bash
B=http://127.0.0.1:8765
J='Content-Type: application/json'
```

1. **The app is served (D21).**
   ```bash
   curl -s -o /dev/null -w '%{http_code} %{content_type}\n' $B/
   ```
   Expected: `200 text/html; charset=utf-8`; the body is byte-identical to `web/dist/index.html`
   and its `/assets/index-*.js` returns `200 text/javascript` `[S1]`.

2. **The library list (LIB-1).**
   ```bash
   curl -s $B/documents | python3 -m json.tool | head -40
   ```
   Expected: one object per document with `segment_count`, `position {segment_id, offset_ms}`,
   `progress` (0..1), `settings {voice_id, speed}` and `last_opened_at`, beside the M1 fields.
   On 2026-10-17: 19 documents, all `ready`; documents 16–19 have 526, 3760, 1858 and 1813 segments;
   every `progress` was 0 and every `settings` was `{voice_id: null, speed: null}` `[S2]`.

3. **Global defaults (LIB-3).**
   ```bash
   curl -s -w '\n' $B/settings
   curl -s -w '\n' -X PUT -H "$J" -d '{"default_voice_id":"af_heart","default_speed":1.0}' $B/settings
   curl -s -w ' %{http_code}\n' -X PUT -H "$J" -d '{"default_voice_id":"af_heart","default_speed":4.0}' $B/settings
   curl -s -w '\n' -X PUT -H "$J" -d '{"default_voice_id":null,"default_speed":1.25}' $B/settings
   ```
   Expected: `{"default_voice_id":null,"default_speed":1.25}` when never set; the first PUT echoes
   its body; speed 4.0 is refused with 422 (`Input should be less than or equal to 3`); the last PUT
   puts the defaults back `[S3]`, `[S7]`.

4. **Position, settings and `opened` (LIB-2, LIB-3).** Document 1 is your copy of the
   `academic_01_seahelm_audio` fixture; segment 11 is its order-10 sentence ("Tamil exhibits the
   largest degradation ...").
   ```bash
   curl -s -X PATCH -H "$J" \
     -d '{"position":{"segment_id":11,"offset_ms":1200},"settings":{"voice_id":"af_bella","speed":1.5},"opened":true}' \
     $B/documents/1
   ```
   Expected: 200 and the summary with `position {segment_id: 11, offset_ms: 1200}`,
   `progress 0.0467` (order 10 of 214 segments), `settings {voice_id: af_bella, speed: 1.5}` and
   `last_opened_at` set to now; `GET /documents` shows the same row `[S6]`. Then the two refusals:
   ```bash
   curl -s -w ' %{http_code}\n' -X PATCH -H "$J" -d '{"position":{"segment_id":215,"offset_ms":0}}' $B/documents/1
   curl -s -w ' %{http_code}\n' -X PATCH -H "$J" -d '{"opened":true}' $B/documents/99999
   ```
   Expected: `segment_id is not a segment of this document 422` (segment 215 belongs to document 2;
   ids in your database may differ, any segment of another document will do) and
   `document not found 404` `[S6b]`, `[S6c]`. Clear it again (`last_opened_at` stays):
   ```bash
   curl -s -X PATCH -H "$J" -d '{"position":null,"settings":null}' $B/documents/1
   ```

5. **Synthesize one clip, then purge it (D19).**
   ```bash
   curl -s -o /dev/null -w '%{http_code}\n' -I "$B/audio/11?voice=af_heart&speed=1.00"
   curl -s -o /tmp/a.wav -w '%{http_code} %{content_type} %{size_download} B %{time_total} s\n' "$B/audio/11?voice=af_heart&speed=1.00"
   curl -s -o /dev/null -w '%{http_code}\n' -I "$B/audio/11?voice=af_heart&speed=1.00"
   (cd api && .venv/bin/python -m yomikoe purge-audio --data-dir ~/yomikoe-m1 \
      --document-id 1 --segment-id 11 --voice af_heart --speed 1.0)
   curl -s -o /dev/null -w '%{http_code}\n' -I "$B/audio/11?voice=af_heart&speed=1.00"
   ```
   Expected: `404` (not cached), `200 audio/wav 223224 B 0.50 s` (Kokoro), `200`,
   `audio cache entries removed: 1`, `404` `[S8]`. Without `--segment-id`, `--voice` or `--speed` the
   command purges every cached clip of the document; it runs beside the live server.

6. **Upload (ING-1) and delete (LIB-4).** Re-uploading bytes that are already in the library returns
   `200` with the existing id, and deleting that id deletes your copy. Your library already holds
   the fifteen `academic_*`, `tables_*` and `report_*` fixtures (documents 1–15), so use a scanned
   one, which is not:
   ```bash
   curl -s -w ' %{http_code}\n' -F file=@api/tests/fixtures/pdfs/scanned_03_zero_trust.pdf $B/documents
   ```
   Expected: `{"id":20,"status":"parsing"} 202` (the id is the next free one). **If you get 200,
   stop: that file is already one of your documents; do not delete it.** Set `ID` to the new id and
   poll:
   ```bash
   ID=20
   curl -s $B/documents/$ID | python3 -m json.tool | grep -E '"(status|pages_done|page_count|segment_count)"'
   ```
   Expected: `ready` within about 2 s, `page_count 2`, `segment_count 0`: the pages are images with
   no text layer and Tesseract is not installed, so OCR is skipped (ING-2, D28) `[S5]`. The same
   upload again returns `{"id":20,"status":"ready"} 200` `[S5b]`. Delete it:
   ```bash
   curl -s -o /dev/null -w '%{http_code}\n' -X DELETE $B/documents/$ID
   curl -s -o /dev/null -w '%{http_code}\n' $B/documents/$ID
   curl -s -o /dev/null -w '%{http_code}\n' -X DELETE $B/documents/$ID
   ls ~/yomikoe-m1/pdfs/e210836729c0*
   ```
   Expected: `204`, `404`, `404`, then `No such file or directory` from `ls` (zsh says `no matches
   found`): the stored PDF is gone; `GET /documents` is
   back to 19 rows `[S9]`. A delete while a document is still `parsing` returns 409 (covered by
   `api/tests/test_lib_gate.py`; not reproduced by hand).

## 4. The app in the browser

Open **http://127.0.0.1:8765/** (the production path: the API serves the built app). The
alternative is the Vite dev server, `cd web && npm run dev`, on http://localhost:5173 with a proxy to
8765 (D21); if 5173 is taken, `npm run dev -- --port 5180`. Use document 1 (or any document whose
position you do not mind changing) for the steps that save a position.

1. **Library (LIB-1).** A table with Title, Pages, Progress, Last opened, Status and a Delete button
   per row; above it an upload control and "Default voice" / "Default speed" (empty voice means
   "(first available)", speed 1.25). Expected on 2026-10-17: 19 rows, row 1
   `academic_01_seahelm_audio | 4 | 0% | just now | ready | Delete` `[W1]`.
2. **Upload from the page.** Choose `api/tests/fixtures/pdfs/scanned_01_seahelm_audio.pdf` (not in
   your library). A new row appears at once (`scanned_01_seahelm_audio | | 0% | never | parsing`),
   then turns ready within a few seconds (polled every 2 s) and takes the PDF's own title,
   `scanned 01 seahelm audio` `[W12]`.
3. **Delete from the page (LIB-4).** On that new row press Delete, then Confirm delete (Cancel backs
   out and keeps the row). The row disappears and the library is back to 19 rows `[W13]`. Do this
   only on the row you just uploaded.
4. **Open and play.** Click `academic_01_seahelm_audio`; the URL becomes `#/doc/1`, the speed reads
   `1.25x` (the global default; the document has no settings of its own) and the voice `af_heart`.
   Click the first word of "Tamil exhibits the largest degradation ...": status goes `playing`, the
   word is highlighted `[W2]`, `[W3]`.
5. **Keyboard (PLAY-6).** Space pauses and resumes. `→` / `←` go to the next / previous sentence
   (from paused, `→` also resumes playing). `Shift+→` / `Shift+←` skip by section: from the last
   sentence of the Abstract, `Shift+→` lands on the heading "1. Introduction", which is short, so the
   highlight moves on to the next sentence about a second later. `=` (or `+`) raises the speed by
   0.25 (`1.25x` → `1.50x`), `-` lowers it, clamped to 0.5–3.0. With the Voice dropdown focused the
   keys do nothing to the player `[W5]`, `[W9]`, `[W10]`.
6. **Remembered settings (LIB-3).** Leave the speed at, say, `1.00x`, reload the page: it still reads
   `1.00x`. Back in the library the Default speed still reads 1.25: the reader's change went to this
   document only `[W8]`.
7. **Position restore (LIB-2).** Play for more than 5 s, pause, reload. The page scrolls to the
   sentence you were on, and Play starts there, a little way into the sentence rather than at its
   first word. `curl -s $B/documents/1` shows the saved `position` (on 2026-10-17:
   `{segment_id: 13, offset_ms: 1996}`, and Play after reopening started at order 12 on the word
   "automatic") `[W6]`, `[W8]`. Positions are saved every 5 s while playing, on pause, and on page
   hide.
8. **Skip toggles (PLAY-8).** Tick "Skip captions" and "Skip references": the affected segments are
   dimmed (4 in document 1, which has captions and no references section), and play, `→` and clicks
   pass over them. Reload: the boxes stay ticked (kept in this browser's localStorage, per document)
   `[W7]`, `[W8]`. Try it on a paper with a References heading to see a whole section dimmed.
9. **Media Session (PLAY-7, manual).** While playing, open the macOS Now Playing widget (Control
   Centre) or, on a phone opened to `http://<your-mac-ip>:8765/` (only if you start the server with
   `--host 0.0.0.0`), the lock screen. It should show the document title and "YomiKoe", and its
   play, pause, previous and next buttons should act like Space and `←` / `→`. Headless Chromium
   confirmed the metadata (`title academic_01_seahelm_audio, artist YomiKoe, state playing`,
   `[W4]`); the widget and lock screen need you.
10. **Reset document 1** when done, if you like:
    `curl -s -X PATCH -H "$J" -d '{"position":null,"settings":null}' $B/documents/1` `[W11]`.

## 5. Number forms by ear (ING-6)

Twelve Kokoro clips (voice `af_heart`, speed 1.0) are in `_agent/results/497_number_forms/`
(`01.wav` to `12.wav`; the table in `index.md` gives source and normalized text):

```bash
cd _agent/results/497_number_forms && for f in *.wav; do echo $f; afplay $f; done
```

Note each one that sounds wrong (for example `$1.10`, `1980s`, `24/7`, `3/4`, `40°C`). The three that
already have rules are 08 (`555-0123` → "555 to 0123"), 11 (`15%` → "15 percent") and 12
(`10-12` → "10 to 12").

## 6. The soak gate

```bash
cd api && YOMIKOE_TEST_SOAK=1 .venv/bin/python -m pytest tests/test_soak_300.py -q -s
```

Expected (gate clause 1): one `SOAK pages=300 segments=6030 parse_wall_s=... rss_self_mb=...
audio_first_last=[200, 200]` line and `1 passed`. On 2026-10-17: parse 6.88 s, RSS 119 MB self and
81 MB children, 7.35 s in all `[S10]`. The test uses `FakeBackend` and a temp data dir; your server
can keep running.

```bash
cd web && source scripts/env.sh && npm run e2e -- --project=chromium tests/e2e/soak.spec.ts
```

Expected (gate clause 2): `[soak]` lines for ingest, first render (under 5 s), the three probe
times, the skip to the last section and the reload restore, then `1 passed`. The harness starts its
own API and Vite on 5173, so stop anything else on 5173 first (including a dev server from
section 4). This step was not re-run in the cold walk because 5173 was in use; the worker run is
`_agent/results/542_soak_browser.txt` (6030 segments, first `.seg` visible 619 ms, restore delta 0
sentences, `1 passed (31.9s)`).

## 7. Docker (gate clause 3, on a machine with Docker)

Follow `docs/DOCKER.md`: `docker compose up --build` from the repo root, then
`curl -i http://localhost:8765/documents` returns `200` and http://localhost:8765/ shows the
library. The first run downloads the pinned Kokoro model into the `hf_home` volume. No container
runtime is installed on the dev machine, so this was not run here.

## 8. What good looks like

- `/` serves the built app; `GET /documents` carries `segment_count`, `position`, `progress`,
  `settings`, `last_opened_at` (section 3).
- PATCH round trip, 422 and 404; settings bounds; purge removes exactly one clip; upload 202 then
  delete 204 (section 3).
- In the page: position and speed survive a reload, keys work and are ignored in form fields, skip
  toggles dim and persist, Media Session shows the title (section 4).
- The soak test passes on both sides; Docker comes up elsewhere (sections 6, 7).

## 9. Known limits

- Documents ingested before M4 keep an empty `sections` table and the reader derives sections from
  heading segments (D25); re-upload (delete, then upload) to get server sections (ING-8) and the
  page-marker and table rules (ING-4, ING-7). `renormalize` does not reclassify.
- `last_opened_at` cannot be cleared through the API.
- OCR needs `tesseract` on PATH (D28); without it scanned pages ingest as empty.
- iOS background playback is unverified; Media Session on a phone needs the server reachable on
  your network.
