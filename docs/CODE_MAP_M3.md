# HearNarro M3 code map: the reader (React, Web Audio, highlight)

This document explains how the M3 reader works end to end and what every file under `web/src`
and `web/tests` does. It is written for an engineer joining the project who has read
`docs/PRD.md` (what), `docs/TECHNICAL_DESIGN.md` (how; D5, D8, D10, D20–D25) and
`docs/CODE_MAP_M2.md` (the audio API the reader consumes).

The design the code was built against is `_agent/specs/m3-reader-interfaces.md` (the spec). Where
the code and the spec differ, this map says what the code does and lists the difference under
"Spec deviations".

## Scope and status

**As of commit `67119ab`** on branch `m3-reader` (prefetch starts after the target clip arrives,
PLAY-5/D19; `web/src/player/usePlayer.ts` last changed there). Updated on 2026-10-17.

### What M3 adds

M2 serves one sentence as audio plus word timestamps. M3 plays a whole document in the browser:

- **PLAY-1** play, pause, skip ±1 sentence, skip ±1 section.
- **PLAY-2** word and sentence highlight in sync with the audio.
- **PLAY-3** click a sentence or a word to seek there.
- **PLAY-4** a voice or speed change mid-play resumes at the current sentence and flushes the lookahead.
- **PLAY-5** gapless playback, no click at segment boundaries.
- Voice and speed pickers, a minimal document picker (not LIB-1), instrumented time-to-first-audio
  (D19 measurement), the browser decode matrix for WAV and Ogg Opus (D16).

No server code changed in M3. The client relies on `GET /documents`, `GET /documents/{id}`,
`GET /documents/{id}/segments`, `GET /voices` and `GET /audio/{segment_id}` exactly as M2 left them
(`docs/CODE_MAP_M2.md` flows a–e).

### The gate

TD "Testing strategy", row "Playback (browser)": Playwright loads a document of at least 30 segments
served by the API with `FakeBackend`, presses play, checks the highlighted word at three probe times
in 20 s, seeks by click and changes speed mid-play. Asserted on Chromium (D22):
`_agent/results/436_e2e_chromium_gate.txt` (9 passed). WebKit and Firefox are reported:
`_agent/results/437_e2e_webkit.txt` (9 passed) and `_agent/results/438_e2e_firefox.txt` (9 passed),
both run with `HEARNARRO_E2E_ALL_ENGINES=1`. Unit tests: `_agent/results/432_unit_green.txt`
(3 files, 58 tests passed). The same e2e suite was red before the UI existed:
`_agent/results/421_e2e_red_chromium.txt` (5 failed, 4 passed).

### Status words

| Word | Meaning |
| --- | --- |
| implemented | Real code; exercised only indirectly or by hand. |
| tested | Real code plus a passing saved run that exercises it (432 unit, 436–438 e2e). |
| fixture | Test data or test harness, not shipped. |
| script | A command-line tool, not shipped in the bundle. |

### Status at a glance

| Piece | Status |
| --- | --- |
| `src/api/client.ts`, `src/api/types.ts` | tested (unit `client.test.ts`, e2e) |
| `src/player/machine.ts` (reducer, D10) | tested (unit `machine.test.ts`, 35 cases) |
| `src/player/schedule.ts` (tokenize, map, locate, findActiveWord, chainStart, nextPlayable, onFetchFailure) | tested (unit `schedule.test.ts`, 21 cases) |
| `src/player/usePlayer.ts` (engine + hook) | tested (e2e only) |
| `src/components/*.tsx`, `src/App.tsx`, `src/main.tsx` | tested (e2e only), except `Picker.tsx` and `Toc.tsx`: implemented |
| `src/styles/app.css` | implemented (contrast computed in `_agent/results/428b_contrast.txt`) |
| `tests/e2e/play.spec.ts` (gate), `decode.spec.ts` (D16 matrix) | green on all three engines (436–438) |
| `web/scripts/measure_first_audio.mjs` (D19) | script; run against Kokoro in `_agent/results/445_first_audio_kokoro.txt` |

## Code flows

Each flow is a numbered list of steps; each step names **file → function**. Shorthand: `engine` is
the `PlayerEngine` instance that `usePlayer` creates once per document view
(`src/player/usePlayer.ts`); `state` is the reducer state (`src/player/machine.ts`); `ctx` is the
`AudioContext`.

### a. Open a document: `#/doc/{id}`

```
browser            App/DocView            client.ts                 API (Vite proxy, D21)
  |-- hashchange --->|                       |                           |
  |                  |-- getDocument ------->|-- GET /documents/{id} --->|
  |                  |-- getAllSegments ---->|-- GET .../segments?from=0&limit=500 (repeat while next_from) -->|
  |                  |-- getVoices --------->|-- GET /voices ----------->|
  |                  |<-- detail, Segment[], Voice[] ------------------- |
  |                  |-- deriveSections; dispatch LOAD  (state idle)     |
  |<-- render Toc, Reader (.seg/.w spans; refs registered), PlayerBar    |
```

1. **Route.** `src/App.tsx` → `useHash()` reads `window.location.hash` through
   `useSyncExternalStore(subscribeHash)`; `App` matches `^#/doc/(\d+)$` and renders
   `<DocView key={id} documentId={id}>`, else `<Picker>` (`src/components/Picker.tsx`, which lists
   `GET /documents` and links only `status == 'ready'` rows). The `key` remounts the view per document.
2. **Player created.** `src/App.tsx` → `DocView` → `usePlayer()` (`src/player/usePlayer.ts`):
   `useReducer(reduce, initialState)`, a `PlayerEngine` in `useState`, a layout effect that mirrors
   every new state into `engine.sync(state)`, and an effect that sets `window.__hearnarro =
   engine.hooks` and listens on `window` for `keydown`, counting only scroll keys outside form
   controls (`schedule.ts` → `isScrollKey`). `Reader` registers `<article class="reader">` through
   `player.registerReaderEl` → `engine.attachReader(el)`, which puts the passive `wheel`/`touchmove`
   listeners on the reading column itself, so scrolling the Toc list never stops follow mode. The same effect listens for `scroll` (capture)
   to refresh the "Back to reading" arrow while not following. Every `engine.scrollTo` opens a self-scroll window (`selfScrollUntil = now + 1200 ms`, ended early by
   `scrollend` or by the target sitting within 2 px of centre for two events); a page `scroll` event outside it, or one inside it that moves
   the target away from centre (`schedule.ts` → `isSelfScroll`, `centreDistance`), turns follow mode off, so the find box, the scrollbar and
   missed gestures stop following while navigate/advance/Back-to-reading scrolls do not (wheel/touchmove/keydown listeners kept).
3. **Load data.** `src/App.tsx` → `DocView` effect → `Promise.all([getDocument, getAllSegments,
   getVoices])` in `src/api/client.ts`. `getAllSegments(id, onPage?, signal?)` follows `next_from`
   with `limit=500` until null and throws `ApiError` if `next_from` does not advance; returns
   segments sorted by `order`. Every request goes through `request()` (15 s timeout chained to the
   caller's `AbortController`; non-2xx → `ApiError{status, url, message}`).
4. **Sections.** `src/components/Reader.tsx` → `deriveSections(apiSections, segments)`: the API's
   `sections` if non-empty, else one section per `type == 'heading'` segment (title = its text,
   `first_segment_id` = its id, level 1) (D25).
5. **LOAD.** `DocView` dispatches `LOAD{documentId, orderedIds, sectionStarts, voice, speed,
   position?}`. Voice = `settings.voice_id`, else the first voice; speed = `settings.speed`, else 1.0;
   `position` only when its `segment_id` is non-null and present in the segments.
   `machine.ts` → `reduce` case `LOAD` (accepted in `idle|error`) sets context, `current` = position
   or the first id, `status = 'idle'`.
6. **Render.** `src/components/Reader.tsx` → `SegmentView` per segment: `tokenize(seg.text)`
   (`schedule.ts`) gives `{token, charStart, charEnd}[]`; the segment renders as
   `<p class="seg seg-{type}" data-id data-order>` (a heading segment that starts a derived section
   renders as `<h2>`/`<h3>` with the same classes) with one `<span class="w" data-i>` per token and a
   single space between tokens. The ref callback calls `registerSegmentEl(id, el, tokens)`, which
   stores the element in `engine.segEls` and the tokens in `engine.tokens`.
   `src/components/Toc.tsx` lists the sections; `src/components/PlayerBar.tsx` renders the controls.

### b. Press Play

```
PlayerBar        usePlayer.play     reduce          engine.build / ensureWindow     client.fetchAudio      API
 |-- click ------->| ensureCtx() (inside the gesture)                                |                    |
 |                 |-- PLAY{at} ----->| idle->loading, generation++, firstAudio.requestedAt
 |                 |  (effect: loading && generation != builtGen) --> build(state)   |                    |
 |                 |                  |               |-- fetch k, k+1, k+2 -------->|-- GET /audio/k ---->|
 |                 |                  |               |<-- AudioClip (decoded) ------|<-- WAV/Ogg + X-Timestamps
 |                 |                  |               | scheduleReady: startClip(k, now+0.05, offset)      |
 |                 |                  |<-- AUDIO_READY{generation, at}  loading->playing, firstAudio.startedAt
```

1. **Gesture.** `PlayerBar` button `#play-pause` (`aria-label` "Play") → `player.play()`
   (`usePlayer.ts`). `engine.ensureCtx()` creates the `AudioContext` inside the click (autoplay
   policy) or resumes a suspended one. From `idle|error` it dispatches `PLAY{at: performance.now()}`.
   From `paused` it chooses: `PLAY` from the first segment if the document had ended; `PLAY` if the
   voice/speed key differs from `engine.builtKey` (a change made while paused, D23); otherwise
   `ctx.resume()` + `RESUME` (D24).
2. **Reducer.** `machine.ts` → `reduce` case `PLAY`: target = event segment or `current`;
   `status = 'loading'`, `generation + 1`, `firstAudio = {requestedAt: at, startedAt: null}`.
3. **Build.** `usePlayer` effect: `state.status == 'loading' && state.generation != engine.builtGen`
   → `engine.build(state)`: records `builtGen` and `builtKey` (`voice|speed.toFixed(2)`), stops and
   disconnects every scheduled source (`clearSchedule`), then `ensureWindow(current.segmentId)`.
4. **Fetch window.** `engine.ensureWindow(fromId)`: wants `[fromId, fromId + PREFETCH_DEPTH]`
   (`PREFETCH_DEPTH = 2`); aborts pending fetches outside it or with another voice/speed key; starts
   `fetchAudio(ctx, id, voice, speed, signal)` for each missing id. Order (67119ab): on a cold play
   only the target is fetched; the two-deep prefetch starts when the target's response resolves (or
   when an already in-flight target resolves). If the target is already decoded, prefetch starts at
   once. Reason: the server serves GETs in arrival order on one synthesis thread, so three GETs
   issued together delay the target (`_agent/results/453_before_reqlog.txt`). `client.ts` → `fetchAudio` builds
   `/audio/{id}?voice=&speed=` with `speed.toFixed(2)` (`audioUrl`), reads `X-Timestamps`
   (`parseTimestamps`), `X-Duration-Ms` and `Content-Type`, decodes a copy of the bytes with
   `ctx.decodeAudioData`, and returns an `AudioClip` with `fetchMs` and `decodeMs`. The server
   synthesizes the target and enqueues the next five (CODE_MAP_M2 §e).
   **Empty clip.** When `X-Duration-Ms` is 0 or the body is at most a 44-byte WAV header
   (`isEmptyAudio`), `fetchAudio` returns `{buffer: null, durationSec: 0}` without calling
   `decodeAudioData`, which rejects a zero-sample WAV; page-marker segments such as `[47]` (empty
   `normalized_text`) arrive this way. **Failed prefetch.** A rejected fetch dispatches `FETCH_FAILED`
   (→ `error`) only when `onFetchFailure(id, engine.targetId)` says the failed id is the segment the
   schedule is blocked on (the play/seek target, or the next clip while buffering); any other failure
   logs `console.warn('hearnarro:skip-segment', {segmentId, reason})` and adds the id to `engine.skipped`.
5. **Start.** On arrival `engine.scheduleReady()` (generation guarded): with an empty schedule it
   calls `startClip(clip, ctx.currentTime + 0.05, offsetSec)`: an `AudioBufferSourceNode`,
   `playbackRate = 1.0` (speed is in the audio, D5), `source.start(when, offset)`, entry
   `{segmentId, source, startAt = when - offset, durationSec = buffer.duration, generation, mapped}`
   where `mapped = mapTimestampsToTokens(tokens, clip.timestamps)`. It highlights the target word at
   once, logs `console.info('hearnarro:first-audio', {ms, speed, voice, segmentId, textLength})`
   and dispatches `AUDIO_READY{generation, at}`.
6. **Playing.** `reduce` case `AUDIO_READY` (generation must match): `status = 'playing'`,
   `firstAudio.startedAt = at`. `PlayerBar` shows "first audio N.NN s" plus the last clip's fetch,
   decode and media type (`lastClip`, set by the engine's `onClip`).

### c. The boundary chain (PLAY-5)

1. **Chain early.** Every time a clip arrives, `engine.scheduleReady()` loops: for the schedule's
   tail entry it takes `orderedIds[idx(tail) + 1]`; if that clip is decoded and the tail has not
   ended, `startClip(clip, tail.startAt + tail.durationSec, 0)` so the audio thread splices
   sample-accurately (`schedule.ts` → `chainStart`). `durationSec` is always the decoded
   `buffer.duration`, never `X-Duration-Ms`. The next id is `nextPlayable(orderedIds, tail, skipped)`,
   so a skipped segment is stepped over, and `ENDED` fires when no playable id is left.
   **Empty clip.** A zero-length clip gets an entry with `durationSec 0` and `source: null` (it stays in
   `window.__hearnarro.entries`), so the next clip chains at the same `startAt` with no gap;
   `startClip` then calls `ensureWindow(emptyId)`, because an entry of zero length is never under the
   clock and so never triggers step 2. Live check on document 17 orders 220–223:
   `_agent/results/463_live_doc17_order222.txt`.
2. **Advance the window.** `engine.tick()` (flow e) notices the segment under the clock changed,
   dispatches `SEGMENT_STARTED{segmentId, generation}` (sets `current`), calls
   `ensureWindow(newId)` (keeps two ahead) and `scheduleReady()`.
3. **Buffering.** If the clock passes the tail's end and the next clip is not decoded, `tick()`
   dispatches `BUFFERING{generation}` (`playing → loading`, generation unchanged, so no rebuild) and
   ensures the window from the next id. When it arrives, `scheduleReady()` starts it at
   `currentTime + 0.05` and dispatches `AUDIO_READY` (back to `playing`). A gap is allowed only here.
4. **End of document.** When the tail is the last id and the clock passes its end, `tick()`
   dispatches `ENDED{offsetMs}` (`playing → paused`, `current` = last id at its duration);
   `engine.ended = true`, so the next Play restarts from the first segment.
5. **Background tab.** Each source's `onended` calls `tick()` if the generation still matches, so
   the chain advances when `requestAnimationFrame` is throttled.

Evidence: the PLAY-5 e2e test reloads, plays the cached document and asserts `|gap| < 1e-6 s` over
at least five consecutive entries of `window.__hearnarro.entries` (436–438).

### d. Seek by click (PLAY-3)

1. **Click.** `src/components/Reader.tsx` → `ReaderImpl.onClick` (one listener on `<article
   class="reader">`): `closest('.seg')` gives the segment id; `closest('.w')` gives `data-i`.
   Calls `onSeek(id, tokenIndex?)` → `DocView.onSeek` → `player.seekTo(segmentId, tokenIndex?)`.
2. **Offset.** `usePlayer.ts` → `seekTo` → `engine.offsetFor(segmentId, tokenIndex)`: the
   `start_ms` of the token's first mapped timestamp when the clip is scheduled or pending, else 0.
3. **Event.** From `idle|error`: `PLAY{at, segmentId, offsetMs}`; otherwise `SEEK{segmentId,
   offsetMs}`. `reduce` case `SEEK` (`playing|paused|loading → loading`, generation + 1).
   Before dispatching, `seekTo` calls `engine.markNavigate()`.
4. **Scroll (navigate).** The `usePlayer` layout effect that syncs the new state calls
   `engine.takeNavigate()`; when set it runs `engine.scrollTo(state.current.segmentId, 'navigate')`
   at once, before any audio arrives. `schedule.ts` → `shouldAutoScroll('navigate', …)` is always
   true, so a click right after scrolling (the Toc, or the reading column) still scrolls. The same
   flag is set by `SKIP`/`SKIP_SECTION` dispatched from `PlayerBar` (the `dispatch` returned by
   `usePlayer` wraps the reducer's), by Play from `idle|error` (the saved position) and by Play after
   the end; each of these also sets `engine.following = true`. Rule: explicit navigation always
   scrolls and resumes follow mode; only the automatic advance (flow e step 5) depends on it. Evidence: before/after live run on document 17,
   `_agent/results/467_live_toc_scroll.txt`.
5. **Rebuild.** The build effect runs flow b steps 3–6 from the target: old sources stopped (their
   `onended` cleared), fetches outside the new window aborted, the target clip started at
   `currentTime + 0.05` with `source.start(when, offsetMs / 1000)`. The server sees a far-away order
   and refills its queue from there (CODE_MAP_M2 §e).

### e. The highlight frame (PLAY-2, D8)

1. **Loop.** `usePlayer` runs a `requestAnimationFrame` loop while `status` is `playing` or
   `loading` (so a buffering schedule keeps highlighting); each frame calls `engine.tick()`.
2. **Locate.** `schedule.ts` → `locate(engine.sorted, ctx.currentTime)`: binary search for the
   entry with the largest `startAt <= currentTime` whose window contains it → `{segmentId,
   elapsedMs}` or null in a gap.
3. **Word.** `schedule.ts` → `findActiveWord(entry.mapped, elapsedMs)`: the token of the last mapped
   timestamp with `start_ms <= elapsedMs` (between words the previous token stays lit). Before the
   first timestamp of a started segment the code shows token 0.
4. **Paint.** `engine.highlight(segmentId, tokenIndex)`: if the `(segment, token)` key changed,
   remove `active` (and `data-active`) from the previous `.seg` and `.w`, add them to the new
   `.seg` (from `engine.segEls`) and its `.w[data-i]`. No React state is read or written.
5. **On segment change.** `SEGMENT_STARTED`, `ensureWindow`, `scheduleReady`, then
   `scrollTo(id, 'advance')`: `scrollIntoView({block: 'center'})`, `behavior: 'auto'` under
   `prefers-reduced-motion`; skipped when `shouldAutoScroll('advance', following)` is false. Follow
   mode (PLAY-2, user request 2026-10-17, replaces the 3 s cooldown): the first wheel/touchmove in the
   reading column or page-scroll key outside a form control sets `following = false`, and the advance
   then never scrolls, however long playback runs, while the highlight keeps moving. Any explicit
   navigation (flow d step 4) or the `PlayerBar` pill `#follow` ("Back to reading ↑/↓", arrow from
   `schedule.ts` → `followHint(rect, innerHeight)`) → `engine.resumeFollowing()` centres the current
   segment at once and sets `following = true`; `window.__hearnarro.following` exposes it.
6. **Position.** At most every 250 ms while `playing`: `POSITION{segmentId, offsetMs}` (the
   readout; M4 persistence will read it).

### f. Speed or voice change (PLAY-4, D23)

1. **Input.** `PlayerBar` `<input id="speed" type="range" min=0.5 max=3 step=0.05>` →
   `snapSpeed(v)` (0.05 multiple in [0.5, 3.0]) → `SET_SPEED{speed}`; `<select id="voice">` →
   `SET_VOICE{voice}`. The readout `#speed-value` shows `speed.toFixed(2) + 'x'`.
2. **Reducer.** `reduce` case `SET_VOICE|SET_SPEED`: in `playing`, `status = 'loading'`,
   generation + 1, `current.offsetMs = 0` (the sentence restarts); in `paused|idle`, context only
   (applied at the next Play, flow b step 1, D23); in `loading|error`, ignored.
3. **Rebuild.** Flow b steps 3–6 at the new key: pending clips with the old key are aborted, the
   current segment and the next two are requested with the new `speed=`/`voice=`, and the server
   clears its queue because the voice/speed changed. The client needs no flush call.

Evidence: the PLAY-4 e2e test waits until the active token is 1..4 of a segment of at least 20
tokens, sets 2.00, and asserts within 1 s that the same segment shows token 0 and that the requests
for that segment and the next carry `speed=2.00` (436–438).

### g. Section skip (PLAY-1, D25)

1. **Buttons.** `PlayerBar` `#prev-section` / `#next-section` → `SKIP_SECTION{by: -1|+1}`;
   `#prev-sentence` / `#next-sentence` → `SKIP{by}`. `Toc` buttons call `onSeek(first_segment_id)`
   (flow d, so from idle they start playback). All four buttons and the Toc mark a navigation, so the
   target segment is scrolled into view and follow mode resumes (flow d step 4).
2. **Target.** `machine.ts` → `sectionTarget(ctx, by)`: section starts mapped to their reading-order
   index; `+1` is the first start after `current`, `-1` the start of the current section if
   `current` is not on it, else the previous start; none → the same state object (no-op).
   `SKIP` clamps `idx(current) + by` to the ends.
3. **Rebuild.** `playing|paused → loading`, generation + 1, offset 0; flow b steps 3–6.

### h. Pause and resume (PLAY-1, D24)

`PlayerBar` "Pause" → `player.pause()`: `ctx.suspend()` and `PAUSE` (`playing → paused`). The
schedule and `currentTime` freeze together; nothing is rebuilt. "Play" while paused with the same
voice/speed → `ctx.resume()` and `RESUME`.

### i. Errors

A failed or timed-out `fetchAudio` (not aborted, still pending) → `FETCH_FAILED{message,
generation: builtGen}` → `error` (stale generations ignored). `PlayerBar` shows the message with
`#retry` (`RETRY`: `error → loading`, generation + 1, same `current`) and `#dismiss` (`DISMISS`:
`error → idle`). Document load errors render `.error-box` in `DocView`/`Picker`.

### j. The e2e harness start-up

1. **Port.** `web/playwright.config.ts` (runner process) picks a free port once with a Node one-liner
   and stores it in `HEARNARRO_E2E_API_PORT` (never 8765, the user's server). `workers: 1`.
2. **Vite.** `webServer`: `npm run dev -- --port 5173 --strictPort --host 127.0.0.1` with
   `HEARNARRO_API=http://127.0.0.1:<port>`; `web/vite.config.ts` proxies `/documents`, `/audio`,
   `/voices` there (D21). The `[WebServer] ... ECONNREFUSED` lines in 436–438 are the decode tests
   loading `/` before the API fixture has started; they are harmless.
3. **API fixture.** `web/tests/e2e/fixtures.ts` → worker-scoped fixture `api`: spawns
   `api/.venv/bin/python -m hearnarro serve --data-dir <mkdtemp> --host 127.0.0.1 --port <port>` with
   `HEARNARRO_TTS_BACKEND=fake`, polls `GET /documents` (30 s), uploads `FIXTURE_PDF`
   (`academic_01_seahelm_audio.pdf`, 198 segments), polls `GET /documents/{id}` until `ready` (60 s),
   provides `{apiBase, documentId}`, and at teardown sends SIGTERM to its own PID (SIGKILL after 5 s)
   and deletes the data dir. The test-scoped `audioRequests` fixture logs every `/audio/` request.
4. **Engines.** Projects `chromium` (launched with `--autoplay-policy=no-user-gesture-required`),
   `webkit`, `firefox`. `play.spec.ts` skips non-Chromium engines unless
   `HEARNARRO_E2E_ALL_ENGINES=1` (D22); `decode.spec.ts` runs everywhere.
5. **Expected word.** `play.spec.ts` derives the expected position from the FakeBackend rule
   (`round(24000 × 80 ms / speed)` frames per `\S+` word of `normalized_text`, words and clips back to
   back) and `window.__hearnarro.{firstStartAt, now()}`, maps the word to a DOM token through the
   API's `X-Timestamps`, and compares with `.w.active` within ±1 word at 3 s, 8 s and 15 s.

## Modules and files

### `web/src/`

| File | Responsibility | Public | Reads / writes | Status |
| --- | --- | --- | --- | --- |
| `main.tsx` | Mounts `<App/>` in `StrictMode` on `#root`; imports `app.css` | none | DOM `#root` | tested (e2e) |
| `App.tsx` | Hash router; `DocView` loads document, segments and voices, dispatches `LOAD`, lays out Toc, Reader, PlayerBar | `default App` | `window.location.hash`; client calls | tested (e2e) |
| `api/types.ts` | Wire and client types: `WordTimestamp`, `Segment`, `Section`, `Voice` (+ optional `backend`), `AudioClip`, `DocumentSummary`, `DocumentDetail`, `DocumentSettings`, `DocumentPosition`, `SegmentsPage` | types | none | tested (typecheck) |
| `api/client.ts` | The only module that builds URLs; 15 s timeout; `ApiError` | `TIMEOUT_MS`, `PAGE_LIMIT`, `ApiError`, `formatSpeed`, `audioUrl`, `segmentsUrl`, `getDocuments`, `getDocument`, `getAllSegments`, `getVoices`, `parseTimestamps`, `fetchAudio` | HTTP via `fetch`; `AudioContext.decodeAudioData` | tested (unit + e2e) |
| `player/machine.ts` | Pure, totally defined reducer (D10): 5 states, 17 events, generation guard | `PlayerStatus`, `PlayerContext`, `PlayerState`, `PlayerEvent`, `initialState`, `indexOf`, `reduce` | none | tested (unit) |
| `player/schedule.ts` | Pure timing helpers (D5, D8) | `Token`, `MappedTimestamp`, `ScheduleEntryView`, `tokenize`, `mapTimestampsToTokens`, `locate`, `findActiveWord`, `ScrollReason`, `shouldAutoScroll`, `FollowHint`, `followHint`, `isScrollKey` | none | tested (unit) |
| `player/usePlayer.ts` | `PlayerEngine` (AudioContext, schedule map, pending fetches, rAF tick, highlight, auto-scroll, instrumentation) and the `usePlayer` hook (reducer + effects + callbacks) | `PREFETCH_DEPTH`, `ScheduleEntry`, `ClipStats`, `HearnarroHooks`, `Player`, `PlayerEngine`, `usePlayer` | `window.__hearnarro`; DOM classes `active`, `data-active`; `console.info('hearnarro:first-audio')`; `/audio` via client | tested (e2e) |
| `components/Picker.tsx` | Document list (M3 minimum, not LIB-1); ready rows link to `#/doc/{id}` | `Picker` | `GET /documents` | implemented (no e2e test renders the picker; the harness test calls `/documents/{id}` through the proxy) |
| `components/Reader.tsx` | Segments as `.seg` with `.w` tokens; registers refs (segments and, via `registerReaderEl`, the reading column for the follow-mode listeners); one click handler for seek; section derivation (D25) | `Reader`, `ReaderProps`, `deriveSections` | DOM | tested (e2e) |
| `components/PlayerBar.tsx` | Transport, "Back to reading" pill `#follow` (shown while not following), voice select, speed slider and readout, `role="status"` word with `data-status`, Retry/Dismiss, stats line | `PlayerBar`, `PlayerBarProps`, `snapSpeed` | reducer state, `lastClip` | tested (e2e) |
| `components/Toc.tsx` | Sections list; click seeks to `first_segment_id` | `Toc`, `TocProps` | none | implemented (no e2e clicks the Toc; live Toc-click scroll check `_agent/results/467_live_toc_scroll.txt`) |
| `styles/app.css` | Tokens on `:root`, dark mode, `.w.active` / `.seg.active` highlight colours with contrast ≥ 4.5:1 | n/a | n/a | implemented (`_agent/results/428b_contrast.txt`) |

### `web/tests/`

| File | Responsibility | Requirement | Status |
| --- | --- | --- | --- |
| `unit/machine.test.ts` | One case per transition row of the reducer, the generation guard, unknown event identity (35 `it`) | D10, PLAY-1, PLAY-3, PLAY-4 | green (432) |
| `unit/schedule.test.ts` | `tokenize` offsets, `mapTimestampsToTokens` on FakeBackend-shaped and spanning timestamps, `locate` with a gap, `findActiveWord` boundaries (16 `it`) | PLAY-2, PLAY-5 | green (432) |
| `unit/client.test.ts` | Spec §1 paths, two-decimal speed in the audio URL, `getAllSegments` paging and sort, `fetchAudio` header parsing and decode-a-copy, `ApiError` on non-2xx, 15 s timeout, caller abort (7 `it`) | PLAY-4 | green (432) |
| `e2e/fixtures.ts` | Worker-scoped API fixture (FakeBackend, temp data dir, upload, ready), `audioRequests` log, `getSegments`, `getDocument` | gate harness | fixture |
| `e2e/play.spec.ts` | The gate: harness proxy check, PLAY-1/2/5 probes, PLAY-3 click, PLAY-4 speed, PLAY-1 transport and sections, PLAY-5 zero gap | PLAY-1..PLAY-5 | green (436; 437, 438 with `HEARNARRO_E2E_ALL_ENGINES=1`) |
| `e2e/decode.spec.ts` | D16 matrix: `decodeAudioData` on `tone.wav` and `tone.ogg`; headless `currentTime` advances. WAV on Chromium asserted, the rest reported | D16 | green (436–438; 422, 423) |
| `e2e/fixtures/make_tone.py`, `tone.wav`, `tone.ogg` | 1 s 440 Hz tone made with the API's `WavEncoder` / `OpusEncoder` | D16 | fixture |
| `e2e/probe_api.py` | Phase 1 probe: starts the API with FakeBackend, uploads the fixture, prints segment counts (`_agent/results/420_api_fixture_probe.txt`) | harness | script |

### `web/` root and scripts

| File | Responsibility | Status |
| --- | --- | --- |
| `package.json`, `package-lock.json` | Exact pinned versions; scripts `dev`, `build`, `typecheck`, `lint`, `format`, `test`, `e2e`. Production dependencies: react, react-dom (closure react, react-dom, scheduler; `_agent/results/440_licence_npm.txt`) | installed (`_agent/results/406_npm_install.txt`) |
| `vite.config.ts` | Dev proxy for `/documents`, `/audio`, `/voices` to `HEARNARRO_API` (default `http://127.0.0.1:8765`, D21); vitest includes `tests/unit/**/*.test.ts` | tested |
| `playwright.config.ts` | Free API port, Vite `webServer`, three engine projects, one worker | tested |
| `tsconfig.json`, `eslint.config.js`, `.prettierrc`, `index.html` | Toolchain config | tested (typecheck 408, lint 409, build 411) |
| `scripts/install_node.sh` | D20: Node `v24.22.0` darwin-arm64 tarball, SHA-256 checked against `SHASUMS256.txt`, into `~/.local/node`; refuses to overwrite | script |
| `scripts/env.sh` | `PATH=$HOME/.local/node/bin:$PATH`, `PLAYWRIGHT_BROWSERS_PATH=$HOME/.local/ms-playwright` | script |
| `scripts/measure_first_audio.mjs` | D19: first-audio wait in the browser against the real server (owned by another worker) | script |

## Data structures

**`PlayerState`** (`machine.ts`): `status` plus `documentId`, `orderedIds`, `sectionStarts`,
`current {segmentId, offsetMs} | null`, `voice`, `speed`, `generation`, `error`,
`firstAudio {requestedAt, startedAt | null} | null`. No audio objects.

**`ScheduleEntry`** (`usePlayer.ts`): `{segmentId, source, startAt, durationSec, generation,
mapped}`. Kept in `engine.entries` (by id) and `engine.sorted` (by `startAt`, capped at 500).
`startAt` is the context time of offset 0 of the clip, so `elapsed = currentTime - startAt`.

**`Pending`** (`usePlayer.ts`): `{key: 'voice|speed', ctrl: AbortController, clip | null}` per
segment id in `engine.pending`; a decoded clip waits here until `scheduleReady` places it.

**`AudioClip`** (`types.ts`): `{segmentId, voice, speed, buffer, timestamps, durationMs, mediaType,
fetchMs, decodeMs}`.

**`window.__hearnarro`** (`HearnarroHooks`): `firstStartAt` (first entry's `startAt`), `now()`
(`ctx.currentTime`), `entries` (getter over `engine.sorted`). Read by the gate and the D19 script.

**DOM contract:** `.seg[data-id][data-order]`, class `seg-{type}`, `.w[data-i]`, `.active` on the
current `.seg` and `.w`, `data-active="true"` on the `.seg`; `role="status"` with `data-status`;
buttons labelled Play/Pause, Previous/Next sentence, Previous/Next section; `#voice`, `#speed`,
`#speed-value`, `#stats`, `#retry`, `#dismiss`.

## Spec deviations

What the code does where it departs from `_agent/specs/m3-reader-interfaces.md`:

1. **`registerSegmentEl` takes a third argument.** Spec §6: `Map<segmentId, HTMLElement>` filled by
   Reader. Code: `registerSegmentEl(id, el, tokens?)`; Reader passes the tokens from `tokenize` so
   the engine can run `mapTimestampsToTokens` when a clip is scheduled (`usePlayer.ts`
   `registerSegmentEl`, `startClip`).
2. **Data loading lives in `App.tsx` `DocView`, not in Reader.** Spec §7: "Reader loads
   `getDocument` + `getAllSegments`; dispatches LOAD". Code: `DocView` loads document, segments and
   voices together, derives sections, dispatches `LOAD`, and passes data down; Reader only renders.
3. **The hook returns more than state and dispatch.** `usePlayer()` returns `{state, dispatch,
   registerSegmentEl, play, pause, seekTo, lastClip}`. `play`/`pause`/`seekTo` exist because the
   `AudioContext` must be created or resumed inside the user gesture and `ctx.suspend()` is a side
   effect outside the reducer; `lastClip` feeds the stats line.
4. **Token 0 is highlighted before the first timestamp.** Spec §6: the active token is the last
   mapped timestamp with `start_ms <= elapsed` (none before the first). Code: `tick()` shows token 0
   once the segment has started, and `scheduleReady()` highlights the target word during the 50 ms
   lead, so the DOM agrees with `playing`.
5. **A heading segment that starts a derived section is rendered as the section title.** Spec §7:
   section titles as headings plus `<p class="seg">` per segment. Code: when the section's title
   equals the heading segment's text, that segment renders as `<h2>`/`<h3>` carrying the `.seg`
   classes and tokens (no duplicated title); other sections get an `<h2 class="section-title">`
   before the segment's `<p>`.
6. **`SET_VOICE` / `SET_SPEED` are dropped during `loading`.** Spec §5 lists only `playing` and
   `paused|idle`; the reducer returns the state unchanged in `loading` and `error`, so a slider
   move while a clip is loading (including while buffering) is lost and the control snaps back.
7. **`window.__hearnarro` is set in every build.** Spec §8 says "dev/test builds only". Code sets it
   unconditionally in the hook's effect (`usePlayer.ts`); it exposes only timing values.
8. **The rAF loop also runs in `loading`.** Spec §6: "while `playing`". Code: `playing` or
   `loading`, so the highlight continues while buffering.
9. **Play after the end restarts from the first segment.** Not in the spec; `engine.ended` makes
   `play()` dispatch `PLAY{segmentId: orderedIds[0]}`.

Against the Technical Design: D10's "Data flow" paragraph (pages of 200 loaded on scroll with an
`IntersectionObserver`) is not built; M3 loads every segment up front in pages of 500 and renders
them all. Virtualised rendering for 10k-segment documents is an M4 item (spec §0, soak test).

## Dependencies and licences

Production closure: react, react-dom, scheduler (3 packages, MIT). Dev: 176 packages; 0 violations
(`_agent/results/440_licence_npm.txt`, `api/scripts/check_licences.py --npm web`). Playwright's
browser binaries are test fixtures, listed, not judged.

## How to run

The commands with expected output are in `docs/M3_TESTING.md`.

## Open items

| Item | Where | Lands in |
| --- | --- | --- |
| D16 default format (WAV vs Ogg Opus): decode matrix passes both on Chromium, Playwright WebKit and Firefox (436–438, 422, 423); pending the user's check in real Safari | `api` settings | decision at M3 close |
| D19 clause chunking at speeds < 1.0: first-audio table in `_agent/results/445_first_audio_kokoro.txt` (before) and `452_first_audio_after.txt` (after 67119ab); decision pending | `synthesis/service.py` or the client | decision at M3 close |
| Settings changes during `loading` are dropped (deviation 6) | `machine.ts` | M4 or a follow-up |
| `sections` table never written; reader derives sections from heading segments (D25) | ING-8 | M4 |
| FastAPI serving `web/dist` (no Vite in production, D21) | `api/hearnarro/app.py` | M4 |
| Position persistence (`PATCH`), remembered settings, keyboard, Media Session | LIB-2, LIB-3, PLAY-6, PLAY-7 | M4 |
| Virtualised rendering and the 300-page soak | `Reader.tsx` | M4 |
| iOS Safari background playback | PRD open question | manual check |
| `Toc.tsx` has no e2e click test | `tests/e2e` | follow-up |
