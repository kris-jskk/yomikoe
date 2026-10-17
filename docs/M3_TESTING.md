# Testing M3 (the reader) by hand

About 30 minutes. You install Node user-local, run the web unit tests, lint, typecheck and build,
run the browser gate on Chromium and the report on WebKit and Firefox, run the decode matrix,
measure first audio against Kokoro, and then open the reader against your own server and listen.
What you are checking is PLAY-1 to PLAY-5 (`docs/PRD.md`): play, pause and skip; word and sentence
highlight in sync; click to seek; a speed change mid-play restarts the sentence at the new speed;
no gap or click between sentences.

All `npm` commands run from `web/`, all `python` commands from `api/`. Every command below was run
on 2026-10-17 by a worker; each section names the saved transcript under `_agent/results/`.

## 1. Prerequisites

Everything from `docs/M2_TESTING.md` section 1 (the `api/.venv` with the `dev` extra, and `tts` for
Kokoro). Node is installed without Homebrew and without sudo (D20):

```bash
bash web/scripts/install_node.sh        # Node v24.22.0 darwin-arm64 into ~/.local/node
source web/scripts/env.sh               # PATH and PLAYWRIGHT_BROWSERS_PATH; do this in every new shell
node --version; npm --version           # v24.22.0, 11.19.1
```

The script downloads the official tarball and `SHASUMS256.txt` from nodejs.org, checks the
SHA-256 (`node-v24.22.0-darwin-arm64.tar.gz: OK`, `_agent/results/403_node_checksum.txt`) and refuses
to overwrite an existing `~/.local/node`. Versions: `_agent/results/404_node_versions.txt`.

```bash
cd web
npm ci                                                       # from package-lock.json, exact pins
npx playwright install chromium webkit firefox               # into ~/.local/ms-playwright (about 1.1 GB)
```

Transcripts: `_agent/results/406_npm_install.txt` (the first install, made with `npm install` while the
lockfile was created; `npm ci` from the committed lockfile was not separately recorded) and
`_agent/results/407_playwright_install.txt` (browser downloads; the exact command line is not in the file).

## 2. Unit tests, typecheck, lint, build

```bash
npm test             # vitest: Test Files 3 passed (3), Tests 58 passed (58)
npm run typecheck    # tsc --noEmit, exit 0
npm run lint         # eslint + prettier --check: "All matched files use Prettier code style!"
npm run build        # dist/index.html and dist/assets/index-*.js (about 220 kB, 69 kB gzip)
```

Transcripts: `_agent/results/432_unit_green.txt`, `408_typecheck.txt`, `409_lint.txt`,
`411_build.txt`.

## 3. The gate, per engine

The harness starts its own API with `FakeBackend` on a free port and a temp data dir, uploads
`academic_01_seahelm_audio.pdf` (198 segments), and starts Vite on 5173 proxying to it. It never
touches port 8765, so your own server can keep running. Stop anything else on 5173 first.

```bash
npm run e2e -- --project=chromium                                    # the gate (D22)
HEARNARRO_E2E_ALL_ENGINES=1 npm run e2e -- --project=webkit          # reported
HEARNARRO_E2E_ALL_ENGINES=1 npm run e2e -- --project=firefox         # reported
```

Without `HEARNARRO_E2E_ALL_ENGINES=1` the six `play.spec.ts` tests are skipped on WebKit and Firefox
(only the three decode tests run there); the gate is asserted on Chromium only in M3 (D22).

Expected: `9 passed` on each engine (three decode tests, the proxy harness test, and the five PLAY
tests). Transcripts: `_agent/results/436_e2e_chromium_gate.txt` (26.5 s),
`437_e2e_webkit.txt` (27.2 s), `438_e2e_firefox.txt` (29.2 s). The
`[WebServer] ... http proxy error: /documents ... ECONNREFUSED` lines at the start are the decode
tests loading `/` before the API fixture is up; they are harmless.

What the five PLAY tests check:

| Test | Requirement | Assertion |
| --- | --- | --- |
| highlighted word at 3 s, 8 s, 15 s | PLAY-1, PLAY-2, PLAY-5 | `.w.active` is the word the FakeBackend clock predicts, within ±1 word |
| click the first token of order 12 | PLAY-3 | within 500 ms the active segment is order 12 and `/audio/{its id}` was requested |
| speed 2.00 mid-play | PLAY-4 | the same segment restarts at token 0 within 1 s; it and the next segment are requested with `speed=2.00` |
| pause/resume, next/previous sentence and section | PLAY-1 | status goes paused/playing; order moves by ±1; section skip lands on the next/previous heading segment (D25) |
| second play, all cached | PLAY-5 | the gap between consecutive scheduled entries is below 1 µs for at least 5 boundaries |

## 4. The decode matrix (D16)

```bash
npm run e2e -- --project=chromium tests/e2e/decode.spec.ts
npm run e2e -- --project=webkit   tests/e2e/decode.spec.ts
npm run e2e -- --project=firefox  tests/e2e/decode.spec.ts
```

Each prints a `DECODE <engine> <file> pass duration=1.0000 s rate=48000` line per file and a
`CLOCK <engine> state=running advanced=0.69x s in 0.700 s` line (headless `currentTime` advances).

| Engine (Playwright) | `tone.wav` | `tone.ogg` (Ogg Opus) | Evidence |
| --- | --- | --- | --- |
| Chromium | pass, 1.0000 s | pass, 1.0000 s | `_agent/results/436_e2e_chromium_gate.txt` |
| WebKit | pass, 1.0000 s | pass, 1.0000 s | `_agent/results/422_decode_webkit.txt`, `437_e2e_webkit.txt` |
| Firefox | pass, 1.0000 s | pass, 1.0000 s | `_agent/results/423_decode_firefox.txt`, `438_e2e_firefox.txt` |

Playwright's WebKit is not Safari. The D16 default-format decision waits on your check in real
Safari (section 7, step 6).

## 5. Licences (npm)

```bash
cd api
.venv/bin/python scripts/check_licences.py --npm ../web | tail -2
# production closure: react, react-dom, scheduler
# TOTAL 179 (prod 3, dev 176)  VIOLATIONS 0 []
```

Transcript: `_agent/results/440_licence_npm.txt` (the output; the command line is not recorded in
the file; `--npm WEBDIR` is the flag in the script's usage line).

## 6. First audio against Kokoro (D19 measurement)

The script opens the reader in headless Chromium against your real server, and for each of 0.5x,
1.0x and 2.0x picks three body segments of 100–200 characters whose clip is not cached
(`HEAD /audio/{id}` → 404), sets the speed, clicks the segment's first word, and records the
hook's `hearnarro:first-audio` log (Play request to first sample scheduled). A second play of one
segment per speed gives the warm (cached) wait.

```bash
# terminal 1 (api/): Kokoro on 8765 with your documents
HEARNARRO_TTS_BACKEND=kokoro .venv/bin/python -m hearnarro serve --data-dir "$HN_DATA" --port 8765
# terminal 2 (web/): Vite on 5180
source scripts/env.sh && npm run dev -- --port 5180
# terminal 3 (repo root)
source web/scripts/env.sh && node web/scripts/measure_first_audio.mjs
# env: HN_API, HN_WEB, HN_DOCS (default 16,17,18,19), HN_VOICE (default af_heart)
```

Result on 2026-10-17, voice `af_heart` (`_agent/results/445_first_audio_kokoro.txt`):

| Speed | Cold samples (ms) | Cold mean | Cold worst | Under 2 s | Warm (ms) |
| --- | --- | --- | --- | --- | --- |
| 0.5x | 6008, 2105, 7162 | 5092 | 7162 | 0 of 3 | 29 |
| 1.0x | 1101, 543, 1411 | 1018 | 1411 | 3 of 3 | 21 |
| 2.0x | 1216, 428, 605 | 750 | 1216 | 3 of 3 | 18 |

After the prefetch-order change (67119ab: prefetch starts once the target clip arrives), a second
run (`_agent/results/452_first_audio_after.txt`):

| Speed | Cold samples (ms) | Cold mean | Cold worst | Under 2 s |
| --- | --- | --- | --- | --- |
| 0.5x | 1968, 2009, 1672 | 1883 | 2009 | 2 of 3 |
| 1.0x | 1057, 2430, 781 | 1423 | 2430 | 2 of 3 |

The two runs measured different segments (n=3 each), so the comparison is indicative, not a
controlled A/B. The request-order change is in `_agent/results/453_before_reqlog.txt`: with the old
code the three GETs (target and two prefetch) start in the same millisecond; after, the target goes
first. The PRD latency target is first audio within 2 s of play. D19 status: decision pending;
supervisor recommendation recorded in the M3 guide.

## 7. The reader against your own server

```bash
# terminal 1 (api/): fake for exact timing, or kokoro for speech
HEARNARRO_TTS_BACKEND=kokoro .venv/bin/python -m hearnarro serve --data-dir "$HN_DATA" --port 8765
# terminal 2 (web/)
source scripts/env.sh && npm run dev        # http://localhost:5173, proxies /documents /audio /voices to 8765 (D21)
```

`HEARNARRO_API=http://127.0.0.1:<port> npm run dev` points the proxy at another server. The API has
no CORS (D21); always open the Vite URL, never the API port, in the browser.

1. Open `http://localhost:5173/`. The picker lists `GET /documents`; ready documents are links.
   `_agent/results/444_server_docs.txt` is what the list returned from the user's server.
2. Open one (`#/doc/{id}`), press Play. The status word goes `loading` then `playing`; the stats
   line shows `first audio N.NN s · fetch … · decode … · format audio/wav`.
3. Watch the highlight: the yellow word follows the voice; the sentence has a pale background; the
   page scrolls to keep it centred unless you scrolled in the last 3 s.
4. Click a word further down: playback jumps there and starts on that word. Click Next/Previous
   sentence and section. Pause and Play resume exactly where they stopped (D24).
5. Move the speed slider while playing: the current sentence restarts at the new speed and the
   readout shows e.g. `2.00x`. Change it while paused: nothing happens until Play (D23).
6. **Safari (D16).** Restart the server with `HEARNARRO_AUDIO_FORMAT=opus` and a fresh data dir,
   open the reader in Safari, and play a few sentences; the stats line should read
   `format audio/ogg`. Report whether it plays and whether boundaries are clean.
7. Listen across at least ten sentence boundaries for gaps or clicks (PLAY-5).

## 8. What good looks like

- `npm test` 58 passed; typecheck, lint and build exit 0 (section 2).
- `9 passed` on Chromium, and on WebKit and Firefox with `HEARNARRO_E2E_ALL_ENGINES=1` (section 3).
- Both formats decode on all three Playwright engines (section 4).
- 0 licence violations (section 5).
- By ear: no gaps or clicks between sentences; the highlight never visibly lags the voice.

## 9. Known limits

- Sections come from heading segments, not the server's `sections` table, which is still empty
  (D25; ING-8 in M4).
- A speed or voice change made while a clip is loading is ignored (`docs/CODE_MAP_M3.md`, deviation 6).
- No position persistence, remembered settings, keyboard shortcuts or Media Session yet (LIB-2,
  LIB-3, PLAY-6, PLAY-7 in M4).
- Every segment is rendered up front; very long documents are not virtualised yet (M4 soak).
- iOS Safari background playback is unverified.
