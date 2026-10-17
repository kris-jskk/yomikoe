# M3 reader interfaces (supervisor-owned)

Written 2026-10-17 at the start of M3, before any worker runs. Source of truth for mechanisms:
`docs/TECHNICAL_DESIGN.md` "Audio delivery and playback (D5)", "Highlight sync (D8)", "Frontend
architecture (D10)", "Testing strategy (D11)" (row "Playback (browser)"); requirements PLAY-1..PLAY-5
in `docs/PRD.md`. Server contract: `docs/CODE_MAP_M2.md` (audio) and `api/hearnarro/routes/documents.py`
(documents, segments). Branch `m3-reader`. App root `web/`. Tests are written against this file before
the code exists. Decisions proposed here are numbered D20..D24 and go into the design decision log and
the PRD when the user confirms them (worker task in phase 3).

## 0. Scope and gate

In scope: PLAY-1 (play, pause, skip ±1 sentence, skip ±1 section), PLAY-2 (word + sentence highlight
in sync), PLAY-3 (click a sentence or word to seek), PLAY-4 (voice/speed change mid-play resumes at the
current sentence and flushes the lookahead), PLAY-5 (gapless, no click at boundaries). Voice and speed
pickers. Instrumented time-to-first-audio (D19 measurement). Browser decode matrix for WAV and Ogg Opus
(D16 decision). A minimal document picker so the user can open their own documents (not LIB-1).

Out of scope (M4): LIB-1 library view, LIB-2 position persistence (`PATCH` does not exist yet),
LIB-3 remembered settings, PLAY-6 keyboard, PLAY-7 Media Session, PLAY-8 skip-block toggles, virtualised
rendering of 10k-segment documents (soak test).

Gate (TD "Playback (browser)"): Playwright loads a document of at least 30 segments served by the API
with `FakeBackend`, presses play, and at three probe times during 20 s of playback the highlighted word
is the expected word; a click on a sentence seeks there; a speed change mid-play restarts the current
sentence at the new speed and the audio URL carries the new speed. All three on Chromium; WebKit and
Firefox are reported, not asserted, in M3.

## 1. Server contract the client relies on (exists, unchanged in M3)

| Call | Returns | Notes |
| --- | --- | --- |
| `GET /documents` | `[{id, title, filename, page_count, pages_done, status, ...}]` | picker |
| `GET /documents/{id}` | summary + `sections: [{id, title, level, first_segment_id}]`, `settings: {voice_id, speed}`, `position: {segment_id, offset_ms}` | `settings`/`position` may be null fields; M3 reads them if present, never writes |
| `GET /documents/{id}/segments?from=&limit=` | `{document_id, total, from, limit, next_from, segments: [{id, order, block_id, type, section_id, text, normalized_text, char_start, char_end}]}` | `limit` clamped to 500; `next_from` null after the last page |
| `GET /voices` | `[{id, name, gender, language}]` (exact keys: read `routes/voices.py`) | picker |
| `GET /audio/{segment_id}?voice=&speed=` | body `audio/wav` or `audio/ogg`; headers `X-Timestamps` (JSON `[{word, start_ms, end_ms, char_start, char_end}]`, offsets into `text`), `X-Duration-Ms` | blocks on a cache miss; 422 bad speed/voice; 502 synthesis failure. Speed: 0.5..3.0 in 0.05 steps, sent with two decimals (`1.25`) |
| `HEAD /audio/{segment_id}?voice=&speed=` | 200 cached / 404 not | never synthesizes; M3 does not use it |

Lookahead: every `GET /audio/k` makes the server synthesize k+1..k+5 at the same voice/speed; a GET
with a different voice/speed or a far-away order clears that document's queue (CODE_MAP_M2 §e). The
client therefore does not need a "flush" call for PLAY-4; it only has to stop requesting the old
voice/speed and request the new one.

**D21 (proposed): dev access without CORS.** The API stays CORS-free. `vite.config.ts` proxies
`/documents`, `/audio`, `/voices` to `http://127.0.0.1:8765` (overridable with `HEARNARRO_API`).
Production serving of `web/dist` by FastAPI is an M4 item.

## 2. Toolchain (phase 0)

**D20 (proposed): Node without Homebrew.** Node LTS from the official tarball on nodejs.org, checksum
verified against `SHASUMS256.txt`, extracted into `~/.local/node` (user-local, no sudo), `~/.local/node/bin`
on `PATH` for every command in `web/`. npm (bundled) with a committed `package-lock.json`. Pinned exact
versions in `package.json` (no `^`). The install script and the PATH line live in `web/scripts/env.sh`
and are documented in `docs/M3_TESTING.md`.

Packages (all MIT/Apache-2.0/BSD; `api/scripts/check_licences.py` gains a `--npm web` mode that walks
`web/node_modules/**/package.json` with the same policy; dev dependencies included; Playwright's browser
binaries are test fixtures, not shipped code, and are listed, not judged):
react, react-dom, typescript, vite, @vitejs/plugin-react, vitest, @playwright/test, eslint + typescript-eslint,
prettier. No component library, no state library, no router (hash route `#/doc/{id}`), no CSS framework.

Commands (each saved under `_agent/results/` when run by a worker):
`npm run typecheck` (`tsc --noEmit`), `npm run lint` (eslint + prettier check), `npm test` (vitest),
`npm run e2e` (Playwright, Chromium by default; `--project=webkit|firefox` for the matrix), `npm run build`.

## 3. Files and ownership

```
web/
  index.html  package.json  package-lock.json  vite.config.ts  tsconfig.json  playwright.config.ts
  eslint.config.js  .prettierrc  scripts/env.sh
  src/main.tsx                 mounts <App/>
  src/App.tsx                  hash route: "#/" picker, "#/doc/{id}" reader
  src/api/types.ts             DocumentSummary, DocumentDetail, Section, Segment, SegmentsPage, Voice, WordTimestamp, AudioClip
  src/api/client.ts            typed fetch wrappers; the only module that builds URLs
  src/player/machine.ts        PlayerState, PlayerEvent, reducer (pure, no DOM, no audio)   (D10)
  src/player/schedule.ts       pure timing helpers: tokenize, mapTimestampsToTokens, locate, findActiveWord
  src/player/usePlayer.ts      the hook: AudioContext, scheduling, prefetch, rAF loop, instrumentation
  src/components/Picker.tsx    document list from GET /documents (M3 minimum, not LIB-1)
  src/components/Reader.tsx    segments as <p class="seg"> with <span class="w"> tokens; click to seek; auto-scroll
  src/components/PlayerBar.tsx play/pause, skip buttons, voice select, speed slider, state + stats readout
  src/components/Toc.tsx       sections list; click = SEEK to first_segment_id
  src/styles/app.css           tokens (light/dark), highlight colours (WCAG AA both themes)
  tests/unit/machine.test.ts   reducer transitions (vitest)
  tests/unit/schedule.test.ts  tokenize / map / locate / findActiveWord (vitest)
  tests/e2e/fixtures.ts        starts API with FakeBackend on a temp data dir, uploads a fixture PDF, waits ready
  tests/e2e/play.spec.ts       the gate (PLAY-1..5)
  tests/e2e/decode.spec.ts     D16 matrix: decodeAudioData on a WAV and an Ogg Opus fixture per browser
```

Workers own whole files; two workers never edit the same file. `_agent/`, `CLAUDE.md`, this spec:
supervisor only.

## 4. Types (`src/api/types.ts`)

```ts
export interface WordTimestamp { word: string; start_ms: number; end_ms: number; char_start: number; char_end: number }
export interface Segment { id: number; order: number; block_id: number; type: string; section_id: number | null; text: string; normalized_text: string; char_start: number; char_end: number }
export interface Section { id: number; title: string; level: number; first_segment_id: number }
export interface Voice { id: string; name: string; gender: string; language: string }
export interface AudioClip { segmentId: number; voice: string; speed: number; buffer: AudioBuffer; timestamps: WordTimestamp[]; durationMs: number; mediaType: string; fetchMs: number; decodeMs: number }
```

`client.ts`: `getDocuments()`, `getDocument(id)`, `getAllSegments(id, onPage?)` (follows `next_from` with
`limit=500` until null; returns `Segment[]` sorted by `order`), `getVoices()`,
`fetchAudio(ctx: AudioContext, segmentId, voice, speed, signal): Promise<AudioClip>` (15 s `AbortController`
timeout; `speed` formatted with `toFixed(2)`; parses `X-Timestamps`; `decodeAudioData` on a copy of the
`ArrayBuffer`; measures `fetchMs` and `decodeMs`). Errors are `ApiError {status, url, message}`.

## 5. Player state machine (`src/player/machine.ts`, D10)

States: `idle | loading | playing | paused | error`. Context (always present):

```ts
interface PlayerContext {
  documentId: number | null
  orderedIds: number[]            // segment ids in reading order (from getAllSegments)
  sectionStarts: number[]         // first_segment_id of each section, in document order (amended 2026-10-17, phase 1)
  current: { segmentId: number; offsetMs: number } | null   // the segment the listener is on, and where in it
  voice: string; speed: number    // speed is a 0.05 multiple in [0.5, 3.0]
  generation: number              // bumped on every schedule rebuild; stale audio events are ignored
  error: string | null
  firstAudio: { requestedAt: number; startedAt: number | null } | null   // D19 instrumentation
}
type PlayerState = { status: 'idle'|'loading'|'playing'|'paused'|'error' } & PlayerContext
```

Events (the whole vocabulary; components dispatch these and nothing else):

```
LOAD{documentId, orderedIds, sectionStarts, voice, speed, position?}
                                idle|error -> idle             (context set, current = position or first id; sectionStarts = first segment id of each section, in order)
PLAY{segmentId?, offsetMs?, at} idle|paused|error -> loading   (target = arg, else current; generation++, firstAudio.requestedAt = at)
AUDIO_READY{generation, at}     loading -> playing             (ignored if generation differs; firstAudio.startedAt = at)
PAUSE                           playing -> paused              (ctx.suspend(); schedule kept)
RESUME                          paused -> playing              (ctx.resume())
SEEK{segmentId, offsetMs=0}     playing|paused|loading -> loading   (generation++, current = target)
SKIP{by: +1|-1}                 playing|paused -> loading      (generation++; target = orderedIds[idx(current)+by], clamped to the ends; offset 0)
SKIP_SECTION{by: +1|-1}         playing|paused -> loading      (generation++; +1: the first sectionStart whose order is greater than current's, or no-op (state unchanged, same object) when there is none; -1: the start of the current section if current is not that start, else the previous section's start, else no-op)
SET_VOICE{voice} / SET_SPEED{speed}
                                playing -> loading             (generation++; current kept, offsetMs = 0: the sentence restarts, PLAY-4)
                                paused|idle -> same state      (context only; applies on next PLAY)
SEGMENT_STARTED{segmentId, generation}   playing -> playing     (current = {segmentId, 0}; ignored if stale)
POSITION{segmentId, offsetMs}   playing -> playing             (from the rAF loop, throttled to 4 Hz; for the position readout and M4 persistence)
BUFFERING{generation}           playing -> loading             (next clip not ready at the boundary; generation unchanged, the schedule continues)
ENDED{offsetMs}                 playing -> paused              (after the last segment; current = last id, offset = the clip's duration, passed by the hook)
FETCH_FAILED{message, generation}  loading|playing -> error    (ignored if stale)
RETRY                           error -> loading               (generation++, same current)
DISMISS                         error -> idle
```

The reducer is pure and totally defined: an event not listed for a state returns the state unchanged.
Unit tests cover every row above and the generation guard.

## 6. Scheduling, prefetch, highlight (`usePlayer.ts` + `schedule.ts`)

One `AudioContext` created on the first PLAY (user gesture; required by autoplay policy). `playbackRate`
is always 1.0; speed is in the audio (D5).

**Schedule entry:** `{segmentId, source: AudioBufferSourceNode, startAt: number, durationSec: number, generation}`
kept in a `Map<segmentId, entry>` in the hook (not in reducer state: it holds audio nodes).

**Building a schedule (on loading):** stop and disconnect every existing source (their `onended` is
ignored because `generation` moved); fetch the target clip (and start prefetch of the next two);
on arrival, if the generation still matches: `t0 = ctx.currentTime + 0.05`,
`source.start(t0, offsetMs / 1000)`, record `startAt = t0 - offsetMs/1000` (so `elapsed = currentTime - startAt`
is the position into the clip), `durationSec = buffer.duration`; dispatch `AUDIO_READY`, then
`SEGMENT_STARTED` when `currentTime >= t0` (checked in the rAF loop, not with a timer).

**Chaining (PLAY-5):** when a clip for the next id arrives and the current entry exists, schedule it at
`startAt_prev + durationSec_prev` exactly, so the audio thread splices sample-accurately. `durationSec`
comes from the decoded `buffer.duration`, never from `X-Duration-Ms` (which is for display). The next clip
is scheduled as soon as it is decoded, even seconds early; every scheduled source has `onended` guarded by
generation and used only as a fallback to advance when the rAF loop is throttled (background tab).

**Prefetch depth:** keep the two segments after the one playing fetched-or-in-flight (D5: two decoded
ahead, server keeps five). A clip whose segment is no longer within `[current, current+2]` after a seek is
dropped (its fetch aborted via its `AbortController`).

**Boundary without a clip:** if `currentTime` passes the end of the last scheduled entry and the next
clip is not decoded yet, dispatch `BUFFERING`; when it arrives, start it at `currentTime + 0.05` (a gap is
allowed when the server is behind; PLAY-5 is asserted on cached audio).

**Pause/resume:** `ctx.suspend()` / `ctx.resume()`. The schedule and `currentTime` freeze together, so
nothing is rebuilt and the resume is sample-exact.

**End of document:** when the last id's entry ends and there is no next id, dispatch `ENDED`.

**Highlight loop (D8):** one `requestAnimationFrame` loop while `playing`. Each frame:
`locate(entries, ctx.currentTime) -> {segmentId, elapsedMs} | null` (the entry with the largest `startAt <= currentTime`
whose window contains it); `findActiveWord(tokenMap, elapsedMs)` (binary search over `start_ms`); if the
(segmentId, tokenIndex) pair changed, remove the two classes from the previous nodes and add them to
`.seg[data-id] .w[data-i]` and its parent; no React re-render on the hot path. The refs are looked up
once per segment change via a `Map<segmentId, HTMLElement>` filled by `Reader` on mount.

**Tokens vs timestamps:** `Reader` renders each segment's `text` split by `tokenize(text) ->
{token, charStart, charEnd}[]` (whitespace split, offsets into `text`). When a clip arrives,
`mapTimestampsToTokens(tokens, timestamps) -> {start_ms, end_ms, tokenIndex}[]` assigns every timestamp to
the token whose `[charStart, charEnd)` overlaps the timestamp's `[char_start, char_end)` (first overlap
wins; a timestamp with no overlap is dropped). The active token is the one of the last mapped timestamp
with `start_ms <= elapsedMs`; between words (after a timestamp's `end_ms`, before the next `start_ms`) the
previous token stays highlighted.

**Auto-scroll:** on segment change, `scrollIntoView({block:'center', behavior:'smooth'})` unless a
`wheel`/`touchmove`/`keydown` was seen in the last 3 s. `prefers-reduced-motion` → `behavior:'auto'`.

**Click to seek (PLAY-3):** a click on `.w` dispatches `SEEK{segmentId, offsetMs = start_ms of the token's
first mapped timestamp if the clip is known, else 0}`; a click elsewhere in `.seg` dispatches `SEEK{segmentId, 0}`.

**Instrumentation (D19 measurement):** `firstAudio.startedAt - requestedAt` is shown in the PlayerBar stats
readout ("first audio 0.83 s") together with the last clip's `fetchMs`, `decodeMs` and `mediaType`, and is
logged with `console.info('hearnarro:first-audio', {ms, speed, voice, segmentId, textLength})`. Phase 3
collects these numbers against Kokoro at 0.5x, 1.0x, 2.0x on the user's documents and the supervisor
decides whether clause chunking (D19) is needed in M3 or deferred.

## 7. Components

- `Picker`: `GET /documents`; rows with title, page_count, status; click → `#/doc/{id}`. Shows only
  documents with `status == 'ready'` as clickable.
- `Reader`: loads `getDocument` + `getAllSegments`; dispatches `LOAD`; renders sections' titles as
  headings where `first_segment_id` matches; `<p class="seg" data-id data-order>` per segment with
  `<span class="w" data-i>` per token and a single space text node between tokens; segment `type` as a
  class (`seg-heading`, `seg-body`, ...). Marks `data-active` on the current segment via the highlight loop only.
- `PlayerBar`: sticky bottom; buttons Play/Pause, ⏮ sentence, ⏭ sentence, ⏮ section, ⏭ section; `<select>`
  voices (from `GET /voices`, default = document `settings.voice_id` or the first voice); `<input type=range min=0.5 max=3 step=0.05>`
  with the value shown as `1.25x`; a status word (idle/loading/playing/paused/error + message, Retry button);
  a stats line (first audio, fetch, decode, format). All controls have `aria-label`s and `id`s so Playwright
  selects by role/label.
- `Toc`: `sections` list; click → `SEEK{first_segment_id, 0}` (and `PLAY` if idle).

**Sections (amended 2026-10-17, phase 1 finding):** the API's `sections` table is never written in M1/M2
(the e2e probe saw 0 sections in every fixture; ING-8 server-side TOC stays an M4 item). In M3 the reader
derives sections client-side: every segment whose `type` is `heading` starts a section, titled by its
`text`, with `first_segment_id = its id`; `sectionStarts` for LOAD is the ordered list of those ids. If the
document endpoint ever returns a non-empty `sections`, it is used instead, unchanged. The Toc and the
section-skip buttons work on the derived list; the e2e PLAY-1 section test asserts against heading
segments (`.seg.seg-heading`).

**Status element:** the PlayerBar status word is rendered in an element with `role="status"` and
`data-status="<state>"`; the e2e tests read it with `getByRole('status')`. The speed readout text is
`<speed.toFixed(2)>x` (e.g. `2.00x`).

Styling: `app.css` with tokens per the artifact-guide pattern; `.w.active { background: var(--hl) }`,
`.seg.active { background: var(--hl-seg) }`, contrast ≥ 4.5:1 on both themes (values recorded in the file).

## 8. Tests

**Unit (vitest, jsdom not needed, pure modules):** `machine.test.ts` one `it` per transition row in §5
plus "stale generation is ignored" and "unknown event is identity"; `schedule.test.ts`: `tokenize`
offsets round-trip, `mapTimestampsToTokens` on FakeBackend-shaped timestamps (evenly spaced, exact token
spans) and on a timestamp spanning two tokens, `locate` with three entries and a gap, `findActiveWord`
boundaries (before first, between words, after last).

**E2E (Playwright).** `fixtures.ts` starts the API (`python -m hearnarro serve --data-dir <tmp> --port <free>`
with `HEARNARRO_TTS_BACKEND=fake`), uploads `api/tests/fixtures/pdfs/<one fixture with ≥ 30 prose segments,
named in the brief>`, polls `GET /documents/{id}` until ready, starts Vite (`webServer` in
`playwright.config.ts` with `HEARNARRO_API` pointing at the temp API). Chromium launches with
`--autoplay-policy=no-user-gesture-required`. Test steps in `play.spec.ts` (requirement IDs in test names):

1. PLAY-1/PLAY-5: open `#/doc/{id}`, click Play, state becomes `playing`; at t = 3 s, 8 s, 15 s read the
   active `.w` (`data-i`) and its segment `data-order`, and compare with the expected position computed
   from the FakeBackend rule (80 ms / speed per word, words back to back, segments back to back, t0 read
   from the page's `window.__hearnarro.firstStartAt`, exposed by the hook in dev/test builds only): the
   expected word index must match within ±1 word at each probe.
2. PLAY-3: click the first token of segment order 12; within 500 ms the active segment is order 12 and
   the request log shows `GET /audio/{id of order 12}`.
3. PLAY-4: while playing, set the slider to 2.00; within 1 s the active segment is unchanged, its first
   token is active, and the next audio request URL contains `speed=2.00`; the request for order+1 also
   carries `speed=2.00` (the lookahead was re-requested at the new speed).
4. PLAY-1: ⏭ sentence advances `data-order` by 1; ⏭ section jumps to a section's `first_segment_id`.
5. PLAY-5: with every clip already cached (second play of the same document), the gap between consecutive
   entries' `startAt + duration` and the next `startAt` is 0 (read from `window.__hearnarro.entries`), for
   at least 5 boundaries.

`decode.spec.ts`: for each browser project, `fetch` `tests/e2e/fixtures/{tone.wav, tone.ogg}` (Ogg Opus
generated once by the API's `OpusEncoder` from a 440 Hz tone, committed) and call `decodeAudioData`;
record pass/fail and `buffer.duration` into the test report. Result table goes in the guide and
`docs/M3_TESTING.md`; the D16 default-format decision is the supervisor's, with the user.

**Risk, named now:** headless Chromium must advance `AudioContext.currentTime` with no output device. If
it does not, the fixture passes `--use-fake-device-for-media-stream --use-fake-ui-for-media-stream` and,
failing that, runs headed in CI-less mode; the worker reports which worked with a saved run.

## 9. Phases and evidence

| Phase | What | Evidence under `_agent/results/` |
| --- | --- | --- |
| 0 toolchain | Node user-local (D20), `web/` scaffold, lint/typecheck/test/e2e/build commands green on an empty app, npm licence mode at 0 violations | node version, `npm run` outputs, licence run |
| 1 red | unit + e2e tests from §8 written and failing for the right reason | red runs |
| 2 build | types, client, machine, schedule, hook, components; unit green | green runs, commit id |
| 3 gate + matrix | e2e green on Chromium; WebKit/Firefox reported; decode matrix; first-audio numbers vs Kokoro at 0.5/1.0/2.0x; `docs/M3_TESTING.md`; `docs/CODE_MAP_M3.md`; PRD + design log sync (D20–D24) | e2e runs, matrix table, measurement file |
| 4 close | hands-on listening check by the user; cost review 2; guide copied to `docs/guide/`; merge to main | ledger, review |

**D22 (proposed):** gate asserted on Chromium only in M3; WebKit and Firefox results reported.
**D23 (proposed):** speed/voice changes while paused apply at the next PLAY without rebuilding anything.
**D24 (proposed):** pause is `AudioContext.suspend()`; the schedule is never rebuilt for pause/resume.
