# HearNarro M2 code map: synthesis, cache, queue and audio API

This document explains how the M2 synthesis code works end to end and what every M2 module and
file does. It is written for an engineer joining the project who has read `docs/PRD.md` (what)
and `docs/TECHNICAL_DESIGN.md` (how) once and now needs to find their way around the code.

M2 was being built while this was first written; the phase updates below bring it to the M2 close. Every module
below carries a status, and every flow step says whether the code for that step exists yet.
Where the code does not exist, the step describes the designed behaviour from the interface
spec (`_agent/specs/m2-synthesis-interfaces.md`) and the Technical Design, and says so.

## Scope and status

**As of commit `9b68eb0`** on branch `m2-synthesis`, plus the working tree read at
2026-10-16 21:27 PDT. At that moment most M2 files were untracked or modified and not yet
committed (`api/hearnarro/app.py` and `api/tests/conftest.py` modified; everything under
`api/hearnarro/synthesis/` except `backend.py`, both new routes, `settings.py` and four test
files untracked). Statuses below describe the files as they were read, not as they were
committed. The per-file inventory, with how each status was decided, is in
`_agent/results/280_m2_code_inventory.txt`.

**Update, phase 2 (service, cache, queue, stretch, audio API; commit "SYN-1 SYN-3 SYN-5 SYN-6: synthesis service ...").** `stretch.py`, `cache.py`, `service.py`, `routes/audio.py`, `routes/voices.py` and the `app.py` lifespan are now real code, tested on the FakeBackend: `_agent/results/297_syn_tests_green.txt` (58 passed, 2 failed, 2 `@model` skipped; the two failures are a test defect, see "Open items"), full suite `_agent/results/300_full_suite.txt`, manual run `_agent/results/302_manual_audio.txt`. Where the code differs from the designed walkthrough below, the step now says what the code does. `KokoroBackend` and `OpusEncoder` remain stubs here (another worker owns them).

**Update, phase 3 (Kokoro backend; commit "SYN-2 SYN-4: Kokoro backend (D15, ...)").** `kokoro_backend.py` is real code: Kokoro-82M on PyTorch CPU at the pinned revision, its own pipeline over the vendored `KModel` (`hearnarro/synthesis/kokoro_model/`, Apache-2.0, 972 lines from `kokoro` 0.9.4, so the `kokoro` package is not a dependency) and base `misaki.en.G2P`, the `num2words` shim (`hearnarro/synthesis/compat/`), and an OOV fallback (misaki lexicon for camel-case pieces, else the vendored g2p_en predictor in `hearnarro/synthesis/g2p_oov/`, else letter spelling). Model tests: `_agent/results/311_model_tests.txt` (30 passed with `HEARNARRO_TEST_MODEL=1`, including the Kokoro gate: TTFA 1842/997/472/483 ms at 0.5/1.0/2.0/3.0 on the 150-character sentence). `scripts/bench.py` is real: `_agent/results/314_bench.txt`, `bench/2026-10-16.json`. OOV demo `_agent/results/315_oov.txt`; cold start 2.34 s `_agent/results/316_cold_start.txt`; licence check 0 violations `_agent/results/310_install_licences.txt`.

**Update, phase 4 (M2 close; commit "SYN-1..SYN-6: Opus encoder (D16), smoke audio pass, M2 testing doc ...").** `OpusEncoder` is real code: Ogg Opus through `opuscodec` 0.1.3 (Apache-2.0, `opus` extra), 48 kbps mono, 24 kHz input taken as is, QEXT off; `HEARNARRO_AUDIO_FORMAT=opus` serves `audio/ogg` with the same `X-Timestamps` as WAV (`_agent/results/333_opus_green.txt`). `scripts/m1_smoke.py --audio` adds an audio pass over the API (335 fake, 336 Kokoro). The hands-on procedure is `docs/M2_TESTING.md`. No module is a stub any more.

### What M2 adds

M1 turns a PDF into ordered sentence segments in SQLite. M2 turns one segment into audio the
browser can play, with word timestamps the reader can highlight against:

- **SYN-1** synthesize one sentence segment at a time, returning audio plus word timestamps.
- **SYN-2** at least six voices across both genders with a language tag, listed by `GET /voices`.
- **SYN-3** speed 0.5x to 3.0x in 0.1 steps: native model speed where supported, time-stretch above.
- **SYN-4** the backend is an interface (`TTSBackend`); Kokoro is the first implementation.
- **SYN-5** a lookahead queue keeps N segments ahead synthesized (N configurable, default 5).
- **SYN-6** synthesized audio is cached so re-listening is instant (P1).
- The `audio_cache` table (already created by M1's initial migration), `GET /audio/{segment_id}`
  with its lookahead queue, `HEAD /audio/{segment_id}`, `GET /voices`.
- A benchmark script reporting real-time factor (RTF) and time-to-first-audio (TTFA).
- A sentence-boundary truth for the 15 text fixtures and a boundary precision/recall metric
  (deferred from M1; see "Sentence boundaries").

### The gate

PRD M2: first audio within 2 s at 0.5x to 3x on CPU. In test form (`test_syn_gate.py`,
tested): a FakeBackend contract version that always runs, and a Kokoro version marked
`@pytest.mark.model` asserting TTFA ≤ 2000 ms at 0.5/1.0/2.0/3.0 on a 150-character sentence.
No RTF or TTFA number has been measured yet: `_agent/results/276_spike_rtf.txt` did not exist
at read time. Both are **to be measured in phase 3**.

### Status words

| Word | Meaning |
| --- | --- |
| planned | No file yet; the spec defines it. |
| stub | The file exists with the final signatures; its public behaviour raises `NotImplementedError` (or, for a constructor, `EncoderUnavailable`). |
| implemented | Real code exists, but no dedicated passing test was seen at read time. |
| tested | Real code plus tests that passed in a saved run (`_agent/results/281_m2_tests_at_read.txt`: 32 passed; also 265, 266, 261). |
| red | A test file written before the code (D11 "gate test first"); the code it exercises is a stub, so it is expected to fail. Not run for this document. |

### Status at a glance

| Piece | Status |
| --- | --- |
| `TTSBackend`, `Voice`, `WordTimestamp`, `SynthResult` (`backend.py`) | tested |
| `FakeBackend` (`fake.py`) | tested |
| `WavEncoder`, `default_encoder` (`encode.py`) | tested |
| `OpusEncoder` (`encode.py`) | tested (333; skipped without the `opus` extra) |
| `stretch_pcm`, `scale_timestamps` (`stretch.py`) | tested (numpy WSOLA, D17) |
| `AudioCache` (`cache.py`) | tested |
| `SynthesisService`, `DbSegmentRepo` (`service.py`) | tested |
| `KokoroBackend` (`kokoro_backend.py`) | tested (`@model`, 311) |
| `GET`/`HEAD /audio`, `GET /voices` (`routes/`) | tested |
| App wiring (`app.py` lifespan, `build_backend`) | tested (through `test_api_audio.py`) |
| `settings.py` | tested |
| Test doubles in `conftest.py` | tested (committed) |
| `boundary_util.py`, `test_syn_boundaries.py` | tested (D18 thresholds asserted) |
| `test_syn1_timestamps.py`, `test_syn3_speed.py`, `test_api_audio.py`, `test_syn_gate.py` (FakeBackend part), `test_stretch.py` | green (297) |
| `test_syn5_queue.py` | green (compares by segment id since commit 5350b46; full suite 338) |
| `test_stretch.py` | WSOLA length within 2 % and pitch kept at 1.05–1.5; short/empty input; `scale_timestamps` order | SYN-3 | green (297) |
| `scripts/bench.py` | tested (314) |
| `scripts/m1_smoke.py --audio` | run (335 fake, 336 Kokoro) |
| `compat/num2words.py`, `g2p_oov/`, vendored `kokoro_model/` | tested (311; `test_compat_num2words.py`) |

## Code flows

Each flow is a numbered list of steps. Each step names **file → function** and what crosses
the boundary (types, HTTP headers, database rows, files on disk). Steps whose code is a stub
or planned say so in brackets; the behaviour described there is the designed one.

Shorthand: `svc` is the `SynthesisService` instance in `app.state.synthesis`; "the synthesis
thread" is the single worker of `app.state.synth_executor`
(`ThreadPoolExecutor(max_workers=1, thread_name_prefix="synth")`).

### a. `GET /audio/{segment_id}?voice=&speed=` on a cache miss

This is the path that decides time-to-first-audio. The browser has asked for a sentence that
has never been synthesized with this voice and speed.

1. **HTTP in.** uvicorn → FastAPI → `api/hearnarro/routes/audio.py` → `get_audio(segment_id: int, voice: str, speed: float, request: Request) -> Response`
   [tested]. FastAPI parses the path and query; a missing `voice` or `speed`, or a non-numeric
   value, is rejected by FastAPI itself with 422 before the handler runs.
2. **Validate speed.** `routes/audio.py` → `get_audio` [tested]. Rule from the spec: `0.5 ≤ speed ≤ 3.0`
   (`MIN_SPEED`, `MAX_SPEED` in the module) and `speed * 10` integral, else 422. The integral
   check must tolerate float error (`2.3 * 10` is `22.999999999999996`), so the designed check
   is "`round(speed * 10)` is within a small epsilon of `speed * 10`", and the value passed on
   is `round(speed, 1)` so every later cache key uses one canonical float.
3. **Validate voice.** `routes/audio.py` → `get_audio` [tested]. `voice` must be one of
   `request.app.state.tts_backend.voices()` ids, else 422. (`FakeBackend.synthesize` would also
   raise `ValueError` for an unknown voice, but the API rejects it before any work is queued.)
4. **Hand to the service.** `routes/audio.py` → `svc.get_audio(segment_id, voice, speed)` in
   `api/hearnarro/synthesis/service.py` → `SynthesisService.get_audio(self, segment_id: int, voice_id: str, speed: float) -> AudioEntry`
   [tested]. Crosses: three plain values.
5. **Load the segment.** `service.py` → `self.repo.get_segment(segment_id)` →
   `DbSegmentRepo.get_segment(self, segment_id: int) -> Segment | None` [tested]. Designed: one
   aiosqlite connection from `Engine.connect()` (`storage/db.py`), a `SELECT` on `segments` by
   primary key, `char_map` BLOB decoded with `unpack_char_map(blob: bytes) -> list[int]`
   (`storage/db.py`). Crosses: a `segments` row → `hearnarro.ingestion.models.Segment`
   (`id, document_id, block_id, order, section_id, text, normalized_text, char_start, char_end, char_map`).
   `None` → the route answers 404.
6. **Cache lookup.** `service.py` → `self.cache.get(segment_id, voice_id, speed, self.backend.name)` →
   `cache.py` → `AudioCache.get(self, segment_id: int, voice_id: str, speed: float, backend: str) -> AudioEntry | None`
   [tested]. Designed: `SELECT` from `audio_cache` on the primary key
   `(segment_id, voice_id, speed, backend)`. Returns `None` here (miss). If the row says `ready`
   but the file is gone, the designed behaviour is to treat it as a miss.
7. **Join an in-flight job or jump the queue.** `service.py` → `get_audio` [tested]. If a lookahead
   job for exactly this key is already running on the synthesis thread, the request awaits that
   job's future instead of starting a second synthesis (Technical Design D5 diagram: "cache hit,
   or wait on in-flight job"). Otherwise this job is placed ahead of every queued lookahead job
   ("the first segment of a play request jumps the queue", SYN-5), so TTFA is one synthesis,
   not six. If the request is a seek (different voice or speed from the document's current
   queue, or an order outside the current window), the service clears and refills the queue
   first; see flow (e). **Code:** the seek check runs first in `get_audio` (`_note_request`): per
   document the service keeps the last requested `(voice, speed, order)`; a request with another
   voice or speed, or an order outside `[last, last + lookahead]`, clears that document's queue
   (log line `seek: document D order j ... queue cleared (n dropped)`). The miss then goes straight to
   the executor; the queue consumer hands the executor one job at a time, so the request waits
   for at most the job in flight. A key already queued is removed from the queue; a key in flight
   is awaited through the in-flight map.
8. **Choose native or stretched.** `service.py` → `get_audio` [tested].
   `lo, hi = self.backend.speed_range()` (`FakeBackend`: `(0.5, 2.0)`). If `speed ≤ hi`, synthesize
   at `speed`. Otherwise synthesize at `hi` and remember `ratio = speed / hi`
   (for 2.1 to 3.0 with `hi = 2.0`: 1.05 to 1.5). See "Speed handling".
9. **Synthesize on the synthesis thread.** `service.py` →
   `await loop.run_in_executor(self._executor, job)` where `job` calls
   `self.backend.synthesize(segment.normalized_text, voice_id, native_speed)` →
   `backend.py` `TTSBackend.synthesize(self, text: str, voice_id: str, speed: float) -> SynthResult`
   (`fake.py` `FakeBackend.synthesize` [tested] or `kokoro_backend.py` `KokoroBackend.synthesize` [tested]).
   Crosses into the thread: a `str` and two scalars. Crosses back: `SynthResult(audio: bytes, sample_rate: int, timestamps: list[WordTimestamp])`;
   `audio` is PCM 16-bit mono little-endian, `timestamps` carry offsets into **`normalized_text`**.
   The event loop is free while this runs.
10. **Stretch (only above native max).** Same job, still on the synthesis thread →
    `stretch.py` → `stretch_pcm(pcm: bytes, sample_rate: int, ratio: float) -> bytes` [tested] and
    `scale_timestamps(ts: list[WordTimestamp], ratio: float) -> list[WordTimestamp]` [tested].
    Crosses: PCM in, PCM about `len/ratio` long out; timestamps with `start_ms`/`end_ms` scaled by
    `1/ratio`, char offsets untouched. **Code:** an in-process numpy WSOLA (Hann frames of 1024
    samples, synthesis hop 512, analysis hop `512 * ratio`, ±256-sample similarity search; D17,
    no new dependency). Times are floored, then clamped to the stretched duration. Both the
    stretched file and the native-max (2.0x) file are cached (spec amendment).
11. **Translate offsets: normalized → text.** `service.py` [tested]. Each `WordTimestamp` from the
    backend has `char_start`/`char_end` into `segment.normalized_text`. The service maps them
    through `segment.char_map` to offsets into `segment.text` (what the reader displays). This is
    **the one place** in the system where offsets change space; see "Data structures" for the rule.
    Crosses: `list[WordTimestamp]` (normalized offsets) → `list[WordTimestamp]` (text offsets).
12. **Encode for the browser.** Same job on the synthesis thread (no ffmpeg anywhere, D16) → `encode.py` → `self.encoder.encode(pcm, sample_rate)` →
    `AudioEncoder.encode(self, pcm: bytes, sample_rate: int) -> bytes`.
    `default_encoder()` returns `WavEncoder` [tested] by default, or `OpusEncoder` [tested] with
    `HEARNARRO_AUDIO_FORMAT=opus` when `opuscodec` is installed (else WAV with a warning).
    Crosses: PCM bytes → container bytes (`audio/wav`, or Ogg Opus `audio/ogg`, D16).
13. **Write through the cache.** `service.py` → `await self.cache.put(entry, audio_bytes)` →
    `cache.py` → `AudioCache.put(self, entry: AudioEntry, audio_bytes: bytes) -> AudioEntry` [tested].
    Designed order: write `data_dir/audio/{document_id}/{segment_id}/{voice_id}_{speed:.1f}.{ext}.tmp`,
    rename to the final name (atomic on one filesystem), then insert the `audio_cache` row with
    `status='ready'`, `path`, `duration_ms`, `timestamps_json` (text offsets), `created_at`.
    Crosses: a file on disk, one row, and the returned `AudioEntry` with `path` filled.
    The file is renamed before the row is inserted, so a row never points at a half-written file.
14. **Respond.** `routes/audio.py` → `get_audio` [tested] builds a `Response`:
    body = the encoded bytes (code: read from `entry.path` with `asyncio.to_thread`),
    `Content-Type: entry.media_type`, `X-Timestamps: <JSON list>`, `X-Duration-Ms: <int>`.
    See "Data structures" for the header shape.
15. **Lookahead enqueue.** `service.py` → `get_audio` [tested], after the response's entry is in
    hand: enqueue the next `lookahead` segments of the same document with the same voice and
    speed. The spec phrases this as `segment_id+1 .. +lookahead`; the repo protocol offers
    `SegmentRepo.segments_from(self, document_id: int, from_order: int, limit: int) -> list[Segment]`,
    which selects by `order` and so stays correct even if segment ids are not contiguous within a
    document. Jobs whose key is already cached are skipped. The queue consumer runs each job on the
    synthesis thread exactly as steps 8 to 13, and the window slides as the browser asks for later
    segments. Crosses: job tuples `(segment_id, voice_id, speed)` into a per-document queue
    bounded at `QUEUE_BOUND = 16` (D9). **Code:** the window is enqueued in a `finally`, so it
    also runs after a failed synthesis; each candidate is checked against the cache, the queue
    and the in-flight map before it is appended. One `collections.deque` holds jobs for all
    documents (the bound of 16 is total); `queue_depth(D)` counts that document's waiting jobs,
    not the one in flight. The window slides on requests (hits and misses), not on job
    completion: the lookahead tests require exactly `k .. k+N` cached after one request.

```
Browser            routes/audio.py        service.py              cache.py / SQLite      synth thread (backend, stretch, encode)
   |                     |                      |                         |                        |
   |-- GET /audio/k ---->|                      |                         |                        |
   |   ?voice&speed      | validate speed/voice |                         |                        |
   |                     |-- get_audio(k,v,s) ->|                         |                        |
   |                     |                      |-- repo.get_segment(k) ->| SELECT segments        |
   |                     |                      |<-- Segment -------------|                        |
   |                     |                      |-- cache.get(k,v,s,b) -->| SELECT audio_cache     |
   |                     |                      |<-- None (miss) ---------|                        |
   |                     |                      |-- run_in_executor(job) (jumps queue) ----------->|
   |                     |                      |                         |   synthesize(normalized_text)
   |                     |                      |                         |   [stretch_pcm + scale_timestamps if s > hi]
   |                     |                      |<-- SynthResult (PCM, ts in normalized offsets) --|
   |                     |                      | translate ts via char_map -> text offsets         |
   |                     |                      |-- encode(pcm) ---------------------------------->|
   |                     |                      |<-- container bytes ------------------------------|
   |                     |                      |-- cache.put(entry, bytes) ->| write .tmp, rename, |
   |                     |                      |                         | INSERT row 'ready'     |
   |                     |<-- AudioEntry -------|                         |                        |
   |<-- 200 body,        |                      |-- enqueue k+1..k+N ----------------------------->| (one at a time)
   |    Content-Type,    |                      |                         |                        |
   |    X-Timestamps,    |                      |                         |                        |
   |    X-Duration-Ms ---|                      |                         |                        |
```

### b. The same call on a cache hit

1. `routes/audio.py` → `get_audio`: validation as in (a) steps 1 to 3 [tested].
2. `service.py` → `SynthesisService.get_audio`: `repo.get_segment(segment_id)` (needed for the
   document id and to answer 404) [tested].
3. `cache.py` → `AudioCache.get(...)` returns an `AudioEntry` with `status == "ready"`, `path`,
   `duration_ms`, `media_type` and `timestamps` already in **text** offsets (they were translated
   before they were stored) [tested].
4. No synthesis, no thread hop. The seek check of (a) step 7 runs first. The service still slides the lookahead window forward (enqueue
   the next N, skipping cached ones), because the browser's prefetch of k+1 and k+2 arrives as
   hits while playback moves on, and the server must keep five ahead [tested].
5. `routes/audio.py` reads the file at `entry.path` (designed: off the event loop, e.g.
   `asyncio.to_thread(path.read_bytes)`, or a `FileResponse`) and returns the same headers as (a)
   [tested]. The test contract (`test_api_audio.py`, tested) asserts the second call is faster than
   the first and that `HEAD` then answers 200.

### c. `HEAD /audio/{segment_id}?voice=&speed=`

1. `routes/audio.py` → `head_audio(segment_id: int, voice: str, speed: float, request: Request) -> Response` [tested]; code: `svc.cached(segment_id, voice, speed)` (never synthesizes, no segment lookup).
2. Same speed and voice validation as GET (code: 422 for HEAD too).
3. `cache.py` → `AudioCache.get(segment_id, voice, speed, backend_name)` [tested].
4. 200 with no body if the entry exists and is `ready`; 404 otherwise, including `failed` rows
   and unknown segments. HEAD **never** synthesizes and never touches the queue; the browser uses
   it to probe cache state without downloading.

### d. `GET /voices`

1. `api/hearnarro/routes/voices.py` → `list_voices(request: Request) -> list[dict[str, Any]]` [tested].
2. Designed: `request.app.state.tts_backend.voices()` → `list[Voice]` → each serialized as
   `{id, name, backend, language, gender}` (the `Voice` dataclass fields). The PRD says "all
   voices across backends"; v1 registers one backend, so the list is that backend's.
3. With `FakeBackend`: six voices, `fake_f1..fake_f3` (female) and `fake_m1..fake_m3` (male), all
   `en-US`. SYN-2 is checked against this list (`test_api_audio.py`, tested: ≥ 6 voices across
   both genders).

### e. Prefetch and seek: what clears the queue and what refills it

The server keeps one lookahead queue per active document. The browser never calls a "prefetch"
endpoint; the server infers intent from the `GET /audio` stream.

1. **Normal playback.** Every `GET /audio/k` (hit or miss) ends with the window sliding to
   `k+1 .. k+N` for the same `(document, voice, speed)`. Jobs already cached are skipped; jobs
   already queued are not duplicated [tested].
2. **Seek, voice change, speed change.** A `GET /audio/j` whose voice or speed differs from the
   document's last request, or whose order is outside `[last, last + N]`, is a seek (code:
   `_note_request` inside `get_audio`; it clears the document's queue, then `j` is synthesized
   and the window `j+1 .. j+N` is enqueued). The explicit form is
   `SynthesisService.prefetch(self, document_id: int, from_order: int, voice_id: str, speed: float) -> None`
   [tested], which **clears the document's queue** and enqueues `from_order .. from_order+N-1`
   (N jobs, so `queue_depth` is at most N right after it returns), and sets the document's last order
   to `from_order`.
3. **What happens to the job already running.** The backend call on the synthesis thread is a
   blocking function and cannot be interrupted. It finishes, its result is cached (useful if the
   user seeks back), and its waiters (if any) receive it. Only queued, not-started jobs are dropped.
4. **Observability.** `SynthesisService.queue_depth(self, document_id: int) -> int` [tested] reports
   how many jobs are queued for a document; tests use it to check "lookahead enqueues N" and
   "seek clears and refills".

```
Browser                     routes/audio.py         service.py (queue for doc D)               synth thread
   |  playing k (voice v, speed 1.0); queue = [k+1 .. k+5]                                         |
   |-- GET /audio/j?v&1.5 ->|                        |                                             |
   |   (speed change)       |-- get_audio(j,v,1.5) ->|                                             |
   |                        |                        | key differs from queue's (v,1.0): seek      |
   |                        |                        |-- prefetch(D, order(j), v, 1.5)             |
   |                        |                        |   clear queue: drop k+2..k+5 (not started)  |
   |                        |                        |   k+1 @1.0 already running -----------------> finishes, cached
   |                        |                        |   refill: [j+1 .. j+5] @1.5 (skip cached)   |
   |                        |                        |-- job j jumps the queue ------------------->| synth j
   |                        |<-- AudioEntry(j) ------|<-------------------------------------------|
   |<-- 200 audio j --------|                        |-- next job j+1 ---------------------------->| synth j+1 ...
```

### f. A backend failure on one sentence

1. On the synthesis thread, `TTSBackend.synthesize` raises (any exception; in tests,
   `SpyBackend(fail_texts={...})` in `conftest.py` raises `RuntimeError("spy backend: induced failure")`).
2. `run_in_executor` re-raises it in the awaiting coroutine in `service.py` [tested].
3. `service.py` logs it with the segment id, then `await self.cache.mark_failed(segment_id, voice_id, speed, backend, reason)` →
   `AudioCache.mark_failed(self, segment_id: int, voice_id: str, speed: float, backend: str, reason: str) -> None` [tested].
   Code: `INSERT OR REPLACE` the `audio_cache` row with `status='failed'`, `path` NULL and
   `timestamps_json = {"failures": n, "reason": ...}` (no migration; spec amendment).
4. **If a request was waiting** (flow a): the service raises
   `SegmentSynthesisFailed(segment_id, reason)` (`service.py`, real class:
   `def __init__(self, segment_id: int, reason: str) -> None`, attributes `segment_id`, `reason`).
   `routes/audio.py` turns it into **502** with JSON `{"segment_id": ..., "reason": ...}` [tested].
5. **If it was a lookahead job**: nothing is waiting; the queue moves on to the next job.
6. The browser (M3) skips a failed segment with 200 ms of silence so playback never stalls.
7. Retry rule (spec amendment, code): an explicit `GET` for a `failed` key retries once; after
   the second failure (`failures >= 2`) the `GET` answers 502 from the row without synthesizing.
   The lookahead queue never retries a failed row.

### g. App start-up and shutdown

`api/hearnarro/app.py` → `create_app(data_dir: Path | None = None, *, max_upload_bytes: int = MAX_UPLOAD_BYTES, executor_factory: Callable[[], Executor] | None = None, tts_backend: TTSBackend | None = None, encoder: AudioEncoder | None = None, lookahead: int | None = None) -> FastAPI`
[tested]. `create_app` registers three routers (`documents`, `audio`,
`voices`) and returns the app; all resources are made in the `lifespan` context manager.

Start-up, in order (current code):

1. `pdf_dir(root).mkdir(...)`; `await asyncio.to_thread(run_migrations, root)` (M1; Alembic
   upgrade to head; `audio_cache` already exists from `0001_initial_schema.py`).
2. `app.state.engine = engine(root)` (aiosqlite connection factory, one connection per request).
3. `app.state.ingest_executor` = `ProcessPoolExecutor(max_workers=2)` (M1, D9), plus
   `ingest_tasks`, `ingest_seconds`.
4. Backend and lookahead: if either `tts_backend` or `lookahead` was not passed,
   `settings.py` → `load_settings(env: Mapping[str, str] | None = None, *, kokoro_installed: bool | None = None) -> Settings`
   reads the environment. `app.py` → `build_backend(settings: Settings) -> TTSBackend` returns
   `KokoroBackend(revision=settings.kokoro_revision)` (imported lazily inside the function, so
   only that module names a model) or `FakeBackend()`.
5. `app.state.tts_backend`, `app.state.encoder` (`encoder` argument or `default_encoder()`),
   `app.state.audio_cache = AudioCache(root, app.state.engine)`.
6. `app.state.synth_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="synth")`.
7. `app.state.synthesis = SynthesisService(backend, app.state.encoder, app.state.audio_cache, DbSegmentRepo(app.state.engine), lookahead=n_ahead, executor=app.state.synth_executor)`.
8. `yield`: the app serves requests.

**Code (phase 2):** `synth_executor` is created first and the backend is built **on the synthesis
thread**: `backend = await loop.run_in_executor(app.state.synth_executor, build_backend, settings)`
(only when no `tts_backend` was injected), so a model load never blocks the event loop (spec
amendment; Technical Design D9 "Startup"). One INFO line logs backend, lookahead and encoder.

Shutdown, in order (current code):

1. `await app.state.synthesis.shutdown()`: clears the queue, cancels the consumer task, then waits
   **at most 5 s** (`SHUTDOWN_WAIT_S = 5.0`) for the in-flight synthesis by awaiting a no-op job on
   the single-worker executor (FIFO, so it completes after the running job).
2. `app.state.synth_executor.shutdown(wait=False, cancel_futures=True)`: no unbounded wait.
3. M1 teardown: process pool shutdown with `cancel_futures=True`, cancel and gather ingestion
   watcher tasks.

The `.tmp` + rename in `AudioCache.put` means a shutdown in the middle of a write leaves at
worst a stray `.tmp` file, never a `ready` row pointing at a truncated file.

### h. The benchmark script's loop

`api/scripts/bench.py` [tested, 314]. As built it calls the backend directly (no service, cache
or encoder), so TTFA is synthesis plus stretch above 2.0x; sentences are 20 body/list lines of
80–200 characters taken round-robin from the fixtures' `expected.jsonl`, normalized. Designed
loop from the spec:

1. Build the configured backend (`load_settings()` → `build_backend()`), and warm it with one
   throwaway synthesis so model load time is excluded ("warm model").
2. Pick 20 sentences from the fixture PDFs (ingested segments, `normalized_text`).
3. For each speed in 0.5, 1.0, 2.0, 3.0, and for each sentence, against an empty cache
   ("cold cache"): time the full miss path of flow (a) (synthesize, stretch if needed, encode,
   write) and record TTFA in ms; record RTF = synthesis wall time / audio duration.
4. Print a table (speed × TTFA and RTF statistics) and write `bench/<date>.json`.

No numbers exist yet; the PRD question "is 2 s TTFA realistic on an M1 laptop" is answered by
this script in phase 3.

### i. The test paths

**FakeBackend-based tests (always run).** Every test except the `@model` ones uses
`FakeBackend` or `SpyBackend` (a `FakeBackend` wrapper in `api/tests/conftest.py` that records
`(text, voice, speed, thread name)` for every call and can add a delay or induce a failure).

- *Unit tests of a single module*: `test_fake_backend.py` (SYN-1/2/3/4 behaviour of the fake),
  `test_encode.py` (WAV header, media type, `default_encoder` returns an `AudioEncoder`),
  `test_settings.py` (env parsing), `test_syn3_speed.py` (red: `scale_timestamps` math,
  `stretch_pcm` length and ratio bounds).
- *Service tests without HTTP or SQLite*: construct `SynthesisService(SpyBackend(...), WavEncoder(), InMemoryCache(), MemorySegmentRepo(segments), lookahead=N, executor=ThreadPoolExecutor(max_workers=1, ...))`
  directly. `InMemoryCache` and `MemorySegmentRepo` (both in `conftest.py`) are duck-typed
  stand-ins for `AudioCache` and `SegmentRepo`. Segments come from
  `synth_fixture_segments()` (all segments of `report_01_zero_trust` as document 1 and
  `academic_01_seahelm_audio` as document 2, ids `document_id * 10_000 + order`) and
  `fifty_fixture_sentences()` (25 non-empty segments from each). `test_syn1_timestamps.py` (tested)
  checks the timestamp invariants at speeds 1.0, 2.0 (native) and 2.5, 3.0 (stretched), and the
  `char_map` translation. `test_syn3_speed.py` (tested) checks the native vs stretched paths through
  the spy's recorded calls. `test_syn5_queue.py` (tested) checks the queue.
- *API contract tests*: `create_app(tmp_path, tts_backend=SpyBackend(), encoder=WavEncoder(), lookahead=N)`,
  enter `app.router.lifespan_context(app)` explicitly (because `httpx.ASGITransport` does not
  send lifespan events; the same pattern as M1's `test_api_documents.py`), then drive it with
  `httpx.AsyncClient(transport=httpx.ASGITransport(app=app))`. Real SQLite and real files under
  the temp data dir. `test_api_audio.py` (tested) and the API part of `test_syn3_speed.py` (tested).

**Model tests (opt-in).** `conftest.py` registers the marker
`model: needs a real TTS model; skipped unless HEARNARRO_TEST_MODEL=1`. The Kokoro smoke test
(synthesize one sentence; audio > 0.3 s; timestamps non-empty) and the Kokoro gate test
(TTFA ≤ 2000 ms at four speeds on a 150-character sentence) carry it. Both are tested (311,
339); `conftest.py` skips them unless `HEARNARRO_TEST_MODEL=1`.

## Modules and files

Signatures are copied from the files as read, or from the spec where the file does not exist.

### `api/hearnarro/synthesis/`

| File | Responsibility | Public functions / classes | Reads | Writes | Status |
| --- | --- | --- | --- | --- | --- |
| `__init__.py` | Package marker | none | none | none | implemented (empty) |
| `backend.py` | The backend interface and its value types (SYN-4) | `class Voice` (`id: str`, `name: str`, `backend: str`, `language: str`, `gender: str`); `class WordTimestamp` (`word: str`, `start_ms: int`, `end_ms: int`, `char_start: int`, `char_end: int`); `class SynthResult` (`audio: bytes`, `sample_rate: int`, `timestamps: list[WordTimestamp]`, property `duration_ms -> int`); `class TTSBackend(Protocol)`: `name: str`, `def voices(self) -> list[Voice]`, `def speed_range(self) -> tuple[float, float]`, `def synthesize(self, text: str, voice_id: str, speed: float) -> SynthResult` | none | none | tested |
| `fake.py` | Deterministic backend for tests and model-free runs | `SAMPLE_RATE = 24_000`, `WORD_MS = 80`; `def frames_per_word(speed: float) -> int`; `class FakeBackend` (`name = "fake"`, `voices`, `speed_range` → `(0.5, 2.0)`, `synthesize`) | none | none | tested |
| `encode.py` | PCM16 → browser container (D7) | `class EncoderUnavailable(RuntimeError)`; `class AudioEncoder(Protocol)`: `media_type: str`, `ext: str`, `def encode(self, pcm: bytes, sample_rate: int) -> bytes`; `class WavEncoder` (`"audio/wav"`, `"wav"`); `class OpusEncoder` (`"audio/ogg"`, `"ogg"`; D16); `def default_encoder(audio_format: str = "wav") -> AudioEncoder` | none | log line (once per process) | tested (`WavEncoder`, `default_encoder`, `OpusEncoder`; 333) |
| `stretch.py` | Speeds above native max (D6, SYN-3) | `MAX_RATIO = 1.5`; `def stretch_pcm(pcm: bytes, sample_rate: int, ratio: float) -> bytes`; `def scale_timestamps(ts: list[WordTimestamp], ratio: float) -> list[WordTimestamp]` | none | none | tested (numpy WSOLA, D17; `test_syn3_speed.py`, `test_stretch.py`) |
| `cache.py` | Write-through audio cache (D7, SYN-6) | `class AudioEntry` (dataclass, see "Data structures"); `class AudioCache`: `def __init__(self, data_dir: Path, db: Engine) -> None`, `async def get(self, segment_id: int, voice_id: str, speed: float, backend: str) -> AudioEntry \| None`, `async def put(self, entry: AudioEntry, audio_bytes: bytes) -> AudioEntry`, `async def mark_failed(self, segment_id: int, voice_id: str, speed: float, backend: str, reason: str) -> None` | `audio_cache` rows; files under `data_dir/audio/` | `audio_cache` rows; audio files (`.tmp` then rename) | tested (`test_api_audio.py`) |
| `service.py` | Orchestration: cache, queue, thread, stretch, translate, encode (SYN-1/3/5/6) | `DEFAULT_LOOKAHEAD = 5`, `QUEUE_BOUND = 16`, `SHUTDOWN_WAIT_S = 5.0`; `class SegmentSynthesisFailed(Exception)`; `class SegmentRepo(Protocol)`: `async def get_segment(self, segment_id: int) -> Segment \| None`, `async def segments_from(self, document_id: int, from_order: int, limit: int) -> list[Segment]`; `class DbSegmentRepo` (`def __init__(self, db: Engine) -> None` + the two methods); `class SynthesisService`: `def __init__(self, backend: TTSBackend, encoder: AudioEncoder, cache: AudioCache, repo: SegmentRepo, *, lookahead: int = DEFAULT_LOOKAHEAD, executor: ThreadPoolExecutor \| None = None) -> None`, `async def get_audio(self, segment_id: int, voice_id: str, speed: float) -> AudioEntry`, `async def prefetch(self, document_id: int, from_order: int, voice_id: str, speed: float) -> None`, `def queue_depth(self, document_id: int) -> int`, `async def shutdown(self) -> None` | `segments` rows (via repo); cache | cache (via `AudioCache`); log | tested (`test_syn1`, `test_syn3`, `test_syn5`; see Open items) |
| `kokoro_backend.py` | The only module that names a TTS model | `MODEL_REPO = "hexgrad/Kokoro-82M"`; `class KokoroBackend` (`name = "kokoro"`, `def __init__(self, revision: str) -> None`, `voices`, `speed_range`, `synthesize`) | model weights from the Hub at the pinned revision | `$HF_HOME` cache | tested (`@model`) |

#### `backend.py`

`backend.py` defines what a synthesis engine is, in four types and nothing else. `TTSBackend` is
a `typing.Protocol`, so a backend does not inherit from anything; it only needs a `name`, a voice
list, a native speed range and a blocking `synthesize`. It is separate so that the service, the
routes and the tests depend on a shape, not on Kokoro. CLAUDE.md makes this a project rule:
`TTSBackend` is the only place a TTS model may be named, and the concrete model lives in one
implementing module (`kokoro_backend.py`) that nothing imports except `app.build_backend` and the
`@model` tests.

Invariants a backend must keep: `SynthResult.audio` is PCM 16-bit mono at `sample_rate`;
`duration_ms` is derived from its length (`len(audio) // 2` frames); timestamps are offsets
into the exact `text` string passed to `synthesize` (the service passes `normalized_text`);
`synthesize` is called only with speeds inside `speed_range()` (the service guarantees this).
`synthesize` is synchronous by design: it runs on the synthesis thread, never on the event loop.
Tested by `test_syn4_fake_backend_satisfies_protocol`, which assigns a `FakeBackend` to a
`TTSBackend`-typed variable and checks `name` and `speed_range()` (the Protocol is not
`runtime_checkable`; conformance is checked statically and by use).

#### `fake.py`

`FakeBackend` produces silence with exactly predictable timing: each whitespace-separated word
(`re.compile(r"\S+")`) gets `frames_per_word(speed) = round(24_000 * 80 / 1000 / speed)` frames,
words back to back, so a 10-word sentence at 1.0x is exactly 800 ms. Timestamps are
`start_ms = i * fpw * 1000 // 24_000`, `end_ms = (i + 1) * fpw * 1000 // 24_000`, and
`char_start`/`char_end` are the regex match's span in `text`. It exists so every service,
queue and API test runs in milliseconds without a model, and so a developer can run the whole
server without Kokoro installed (`HEARNARRO_TTS_BACKEND=fake`).

It enforces the same contract a real backend must: an unknown `voice_id` raises `ValueError`,
a speed outside `(0.5, 2.0)` raises `ValueError` (so a service bug that passes 2.5 to the backend
fails loudly instead of silently "working"), and empty or whitespace-only text returns a
`SynthResult` with zero bytes and no timestamps. It is deterministic: same input, same bytes.
Tested by `test_fake_backend.py` (protocol, six voices both genders `en-US`, 80 ms per word over
speed, even timestamps with exact char spans, determinism, unknown voice, out-of-range speed,
empty text); passing in `_agent/results/281_m2_tests_at_read.txt`.

#### `encode.py`

`encode.py` turns PCM into bytes a browser can decode with `AudioContext.decodeAudioData`
(D5, D7). It is separate because the container choice is the most licence-constrained decision
in M2 (see "Dependencies and licences"), and isolating it means swapping WAV for Opus changes
one module and one `media_type`, not the service or the route. `WavEncoder` uses only the stdlib
`wave` module, rejects a PCM buffer with an odd byte count (`ValueError`), and is always
available, so tests and a fresh checkout work with no native dependency.

`OpusEncoder` writes Ogg Opus through `opuscodec` (Apache-2.0; the `opus` extra): 48 kbps,
mono, QEXT off, the 24 kHz PCM passed as is (libopus accepts 8/12/16/24/48 kHz input; decoders
play at 48 kHz). Its constructor imports `opuscodec` and raises `EncoderUnavailable` if it is
missing; `default_encoder("opus")` then falls back to `WavEncoder` with a warning, and logs the
choice once per process (a module global `_logged`). An empty PCM buffer becomes one 20 ms
silent frame because `opuscodec` refuses to flush an empty stream. Tested by `test_encode.py`
(WAV header: 24 kHz, mono, 16-bit, data length; media type and empty input; Opus: `OggS` and
`OpusHead`, under 20 % of the WAV size for 1 s, empty input) and by
`test_api_audio.py::test_syn1_audio_format_opus_serves_ogg_same_timestamps_d16`; the Opus tests
skip when `opuscodec` is not installed.

#### `stretch.py`

`stretch.py` handles 2.1x to 3.0x, which the model cannot produce cleanly (D6: Kokoro's duration
predictor clips consonants above 2.0x). The service synthesizes at the backend's native maximum
and stretches by `ratio = requested / native_max`, bounded `1.0 < ratio ≤ 1.5` (`MAX_RATIO`), a
range in which tempo change without pitch change is low-artefact. It is separate because the
implementation is undecided (ffmpeg `atempo` subprocess vs an in-process WSOLA) and the rest of
the code must not care which.

Invariants: `stretch_pcm` keeps pitch, returns PCM16 mono of length about `len(pcm) / ratio`,
and rejects a ratio outside `(1.0, 1.5]` (the red test checks 0.9, 1.0, 1.6, 3.0 are rejected).
`scale_timestamps` multiplies `start_ms` and `end_ms` by `1/ratio`, returns ints, keeps order and
leaves `char_start`/`char_end` untouched; the red test asks each scaled value to be within 1 ms
of exact. Both functions are pure and run on the synthesis thread. Tests: `test_syn3_speed.py`
and `test_syn1_scaled_timestamps_keep_invariants` (both red).

#### `cache.py`

`AudioCache` is the only code that touches `audio_cache` rows and audio files. It is
write-through: synthesize, encode, write file, insert row, then return (Technical Design
"Cache"). It is separate so the service can be tested against `InMemoryCache` with no SQLite
and no disk, and so the on-disk layout lives in one place. The key is
`(segment_id, voice_id, speed, backend)`, the table's primary key; `segment_id` rather than a
text hash means a re-ingested document never reuses stale audio, and `ON DELETE CASCADE` on
`segments(id)` removes rows when a document is deleted (the files need a matching delete; see
"Open items").

Invariants: a `ready` row always points at a complete file (write `.tmp`, rename, then insert);
stored timestamps are in text offsets; `speed` is stored as the canonical one-decimal value
(the `InMemoryCache` double rounds with `round(speed, 1)`, and the real cache must match it or a
float like `2.3000000000000003` will miss). `mark_failed` records a `failed` row with no path.
Failure behaviour: a disk or database error propagates to the service, which treats it like a
synthesis failure for that request. Tested (when implemented) through `test_api_audio.py`
against a temp data dir.

#### `service.py`

`SynthesisService` is the conductor. It owns the backend, the encoder, the cache, the segment
repo, the per-document lookahead queues and the one-thread executor. It decides native vs
stretched speed, runs the blocking work on the synthesis thread, translates timestamp offsets
from `normalized_text` to `text` through `char_map`, writes through the cache, and keeps the
lookahead window full. It imports no model: `backend` arrives as a `TTSBackend`.

`SegmentRepo` is a Protocol so the service reads segments without importing aiosqlite; the
production `DbSegmentRepo` reads the `segments` table through the M1 `Engine` and unpacks
`char_map`; tests use `MemorySegmentRepo`. `SegmentSynthesisFailed` is the one exception the
route maps to 502. Invariants: synthesis only ever runs on the executor (the spy records the
thread name, so tests can assert it ran on a `synth*` thread); one key is never synthesized twice
concurrently; the queue for a document is bounded at 16; a seek drops queued, not-started jobs.
Failure: see flow (f). Tests: `test_syn1_timestamps.py`, `test_syn3_speed.py` (tested),
`test_syn5_queue.py` (tested).

#### `kokoro_backend.py`

The only file that may name a TTS model (`MODEL_REPO = "hexgrad/Kokoro-82M"`, Apache-2.0) [tested].
`KokoroBackend(revision=PINNED_REVISION)`; `settings.DEFAULT_KOKORO_REVISION` holds the same D15
hash and is used when `HEARNARRO_TTS_BACKEND=kokoro` names no revision and the `tts` extra is
installed. Construction (on the synthesis thread) registers the `num2words` shim, imports torch
and `misaki.en`, fetches `config.json` and `kokoro-v1_0.pth` with `hf_hub_download(revision=...)`,
builds the vendored `KModel` and the US `G2P` (spaCy `en_core_web_sm`); the GB `G2P` and each
voice pack (`voices/<id>.pt`, same revision) load on first use. `voices()` lists 10 voices
(`af_heart` first; af/am en-US, bf/bm en-GB; gender from the second letter); `speed_range()` is
`(0.5, 2.0)`. `synthesize` runs under a lock: G2P → tokens, phonemes filtered to Kokoro's vocab,
chunks of ≤ 510 phonemes cut at sentence then clause punctuation, one `KModel` call per chunk
with `pack[len(ps) - 1]`, and token times from `pred_dur` (25 ms frames; a token spans its own
phoneme characters). `kokoro.pipeline` is never imported, which also avoids upstream
`join_timestamps`' misalignment after empty-phoneme tokens (spike 274).

Word rule: one `WordTimestamp` per whitespace-delimited word of the input, `(char_start,
char_end)` = that slice; start = first timed token's start, end = last timed token's end; a word
with no timed token gets a zero-length interval at the previous word's end; times are clamped to
be non-decreasing and ≤ duration. OOV words (misaki returns no phonemes): `_OOVFallback` splits
camel case and a possessive `'s`, looks pieces up in misaki's gold/silver lexicon, else predicts
ARPAbet with the vendored g2p_en GRU and maps it to Kokoro IPA (`arpabet_to_kokoro`), else spells
the letters; one `WARNING` per OOV word naming the phonemes and the method. Tests:
`test_kokoro_backend.py` (pure helpers always; model tests `@pytest.mark.model`),
`test_syn_gate.py` (smoke and gate), `test_compat_num2words.py`.

### `api/hearnarro/routes/`

| File | Responsibility | Public functions | Reads | Writes | Status |
| --- | --- | --- | --- | --- | --- |
| `audio.py` | Audio endpoints (SYN-1/3/5/6, D5) | `router = APIRouter()`; `MIN_SPEED = 0.5`, `MAX_SPEED = 3.0`; `@router.get("/audio/{segment_id}") async def get_audio(segment_id: int, voice: str, speed: float, request: Request) -> Response`; `@router.head("/audio/{segment_id}") async def head_audio(segment_id: int, voice: str, speed: float, request: Request) -> Response` | `app.state.synthesis`, `app.state.tts_backend`, `app.state.audio_cache` (designed) | HTTP response | tested |
| `voices.py` | Voice list (SYN-2) | `router = APIRouter()`; `@router.get("/voices") async def list_voices(request: Request) -> list[dict[str, Any]]` | `app.state.tts_backend.voices()` (designed) | HTTP response | tested |
| `documents.py` | M1 document endpoints | unchanged in M2 (the spec: `GET /documents/{id}` and the list gain nothing new) | `documents`, `sections`, `segments` | `documents`, PDF files | implemented (M1) |

### `api/hearnarro/storage/` (as touched by M2)

| File | M2 relevance | Public functions used by M2 | Status |
| --- | --- | --- | --- |
| `db.py` | Connection factory and `char_map` codec | `class Engine` with `async def connect(self) -> AsyncIterator[aiosqlite.Connection]` (context manager; WAL, foreign keys, busy timeout 10 s); `def engine(data_dir: Path) -> Engine`; `def resolve_data_dir(data_dir: Path \| str \| None) -> Path` (used by `settings.py`); `def unpack_char_map(blob: bytes) -> list[int]` (packed little-endian uint16) | implemented (M1, unchanged) |
| `repo.py` | M1 query helpers plus M2 segment lookups | `async def get_segment_row(conn, segment_id: int) -> dict \| None`, `async def segment_rows_from(conn, document_id: int, from_order: int, limit: int) -> list[dict]` (both include `char_map`; used by `DbSegmentRepo`); `AudioCache` holds its own SQL | implemented (M1) + M2 additions, tested |
| `jobs.py` | M1 ingestion worker in the process pool | none; M2 does not touch ingestion | implemented (M1, unchanged) |
| `migrations/versions/0001_initial_schema.py` | Created `audio_cache` with the D7 DDL in M1 | n/a; M2 needs no migration unless the schema changes (then via Alembic, per CLAUDE.md) | implemented (M1) |

### `api/hearnarro/settings.py` and `api/hearnarro/app.py`

| File | Responsibility | Public functions / classes | Reads | Writes | Status |
| --- | --- | --- | --- | --- | --- |
| `settings.py` | Runtime configuration from env vars | `BACKEND_ENV`, `KOKORO_REVISION_ENV`, `LOOKAHEAD_ENV`, `DATA_DIR_ENV`, `DEFAULT_LOOKAHEAD = 5`, `BACKENDS = ("fake", "kokoro")`; `class SettingsError(ValueError)`; `class Settings` (frozen: `tts_backend: str`, `kokoro_revision: str \| None`, `lookahead: int`, `data_dir: Path`); `def kokoro_available() -> bool`; `def load_settings(env: Mapping[str, str] \| None = None, *, kokoro_installed: bool \| None = None) -> Settings` | `os.environ`; whether the `kokoro` package is importable | warning log when falling back to fake | tested |
| `app.py` | App factory and lifespan | `def build_backend(settings: Settings) -> TTSBackend`; `def create_app(...) -> FastAPI` (signature in flow g) | settings | `app.state.*` | tested |

`load_settings` rules: an explicit `HEARNARRO_TTS_BACKEND` wins and must be `fake` or `kokoro`
(else `SettingsError`); `kokoro` then requires `HEARNARRO_KOKORO_REVISION` (else `SettingsError`).
Unset: `kokoro` only when the package is installed **and** a revision is pinned, otherwise `fake`
with a warning naming why. `HEARNARRO_LOOKAHEAD` must be an integer ≥ 0. The `env` and
`kokoro_installed` parameters exist so tests never depend on the real environment. Tested by
`test_settings.py` (defaults, explicit choice, invalid values, lookahead and data dir).

### `api/scripts/bench.py`

| File | Responsibility | Public interface | Reads | Writes | Status |
| --- | --- | --- | --- | --- | --- |
| `bench.py` | TTFA and RTF for the configured backend (PRD M2) | CLI script; see flow (h) | fixture `expected.jsonl` files | stdout table; `bench/<date>.json` | tested (314) |

### `api/tests/` (M2 files)

| File | What it covers | Requirement IDs | Status |
| --- | --- | --- | --- |
| `conftest.py` (M2 part) | `pytest_configure` registers the `model` marker; `SpyBackend(delay_s: float = 0.0, fail_texts: set[str] \| None = None)`; `InMemoryCache`; `MemorySegmentRepo(segments: list[Segment])`; `synth_fixture_segments() -> tuple[Segment, ...]`; `fifty_fixture_sentences() -> list[Segment]`; `PDF_FIXTURES`, `SYNTH_FIXTURE_STEMS` | SYN-1..6 helpers | implemented, uncommitted |
| `test_fake_backend.py` | FakeBackend contract | SYN-1, SYN-2, SYN-3, SYN-4 | tested |
| `test_encode.py` | WavEncoder and default_encoder | SYN-1 | tested |
| `test_settings.py` | env parsing | SYN-4, SYN-5 | tested |
| `test_syn1_timestamps.py` | timestamp invariants on 50 fixture sentences, native and stretched; char_map translation | SYN-1 | green (297) |
| `test_syn3_speed.py` | `scale_timestamps` math; `stretch_pcm` length and ratio bounds; native vs stretched path; API speed validation | SYN-3 | green (297) |
| `test_syn5_queue.py` | lookahead enqueues N; seek clears/refills; cached jobs skipped; first request jumps the queue | SYN-5 | 8 of 10 green; 2 fail on a fixture text collision (`_agent/results/299_queue_test_text_collision.txt`) |
| `test_stretch.py` | WSOLA length within 2 % and pitch kept at 1.05–1.5; short/empty input; `scale_timestamps` order | SYN-3 | green (297) |
| `test_api_audio.py` | HTTP contract: miss then hit, headers, 404/422/502, HEAD, `/voices` ≥ 6 both genders | SYN-1, SYN-2, SYN-6 | green (297) |
| `test_syn_gate.py` | Gate: FakeBackend contract always; Kokoro TTFA ≤ 2000 ms at four speeds (`@model`) | M2 gate | green (FakeBackend part, 297); `@model` skipped |
| `boundary_util.py` | Sentence-boundary metric | ING-5, SYN-1 | tested |
| `test_boundary_util.py` | Metric unit tests | ING-5 | tested |
| `test_syn_boundaries.py` | Truth files keep the expected word stream; prints per-fixture P/R/F1 (not asserted) | ING-5, SYN-1 | tested (measurement) |

## Data structures

### `WordTimestamp` (`backend.py`)

```python
@dataclass(frozen=True)
class WordTimestamp:
    word: str
    start_ms: int
    end_ms: int
    char_start: int  # offsets into the text passed to synthesize()
    char_end: int
```

Half-open character span `[char_start, char_end)`. Times in milliseconds from the start of that
segment's audio. Invariants (SYN-1, Technical Design "Testing strategy"): sorted by `start_ms`,
non-overlapping, last `end_ms ≤ duration_ms`, and every `(char_start, char_end)` lies inside the
string it refers to.

### `SynthResult` (`backend.py`)

```python
@dataclass
class SynthResult:
    audio: bytes  # PCM 16-bit mono
    sample_rate: int  # 24_000 for Kokoro
    timestamps: list[WordTimestamp] = field(default_factory=list)

    @property
    def duration_ms(self) -> int:
        frames = len(self.audio) // 2
        return int(frames * 1000 / self.sample_rate)
```

Lives only between the backend and the service, on the synthesis thread. Never cached, never
sent to the browser.

### `Voice` (`backend.py`)

```python
@dataclass(frozen=True)
class Voice:
    id: str
    name: str
    backend: str
    language: str  # BCP-47, e.g. "en-US"
    gender: str  # "female" | "male" | "neutral"
```

Serialized field for field by `GET /voices`.

### `AudioEntry` (`cache.py`)

```python
@dataclass
class AudioEntry:
    segment_id: int
    voice_id: str
    speed: float
    backend: str
    status: str  # "ready" | "failed"
    path: Path | None
    media_type: str
    duration_ms: int
    timestamps: list[WordTimestamp]  # offsets into Segment.text
    document_id: int = 0  # for the file path (spec amendment)
    failures: int = 0     # failed rows: explicit attempts that failed
```

The service's return value and the cache's unit. `media_type` is not a column: `AudioCache.get`
derives it from the file extension (`.wav` → `audio/wav`, `.ogg`/`.opus` → `audio/ogg`).
`document_id` comes from the segment row when the service builds the entry; on `get` it is read
back from the file path. The two new fields have defaults so positional construction (the
test doubles) keeps working.

### The `audio_cache` row (D7 DDL, `migrations/versions/0001_initial_schema.py`)

```sql
CREATE TABLE audio_cache (
  segment_id INTEGER NOT NULL REFERENCES segments(id) ON DELETE CASCADE,
  voice_id TEXT NOT NULL, speed REAL NOT NULL, backend TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('ready','failed')),
  path TEXT, duration_ms INTEGER, timestamps_json TEXT,
  created_at TEXT NOT NULL,
  PRIMARY KEY (segment_id, voice_id, speed, backend)
)
```

`timestamps_json` holds the same JSON list as the `X-Timestamps` header (text offsets).
`path` and `duration_ms` are NULL for `failed` rows.

### Cache file layout

```
<data_dir>/                         HEARNARRO_DATA_DIR or ./data
  hearnarro.db                      SQLite (WAL)
  pdfs/ ...                         M1 uploads
  audio/
    {document_id}/
      {segment_id}/
        {voice_id}_{speed:.1f}.{ext}        e.g. fake_f1_1.0.wav, af_heart_2.5.webm
        {voice_id}_{speed:.1f}.{ext}.tmp    only during a write; renamed, never served
```

One file per `(segment, voice, speed)`. The backend name is in the row key but not in the file
name, so switching backends with the same voice id would overwrite a file; voice ids are
backend-specific in practice (`fake_*` vs Kokoro's ids), so this does not collide today.
Grouping by document makes LIB-4 (delete a document and its audio) one directory removal.

### `X-Timestamps` header

`GET /audio` returns:

```
Content-Type: audio/wav            (audio/ogg with HEARNARRO_AUDIO_FORMAT=opus)
X-Duration-Ms: 2480
X-Timestamps: [{"word":"Zero","start_ms":0,"end_ms":80,"char_start":0,"char_end":4}, ...]
```

The JSON is a list of `WordTimestamp` fields in order, offsets into **`Segment.text`**. HTTP
header values are Latin-1, so the JSON must be serialized with `ensure_ascii=True` (Python's
`json.dumps` default), which escapes words like "naïve" as `ï`. The header grows with the
sentence's word count; whether a very long sentence hits a server or browser header-size limit
has not been measured (Open items). The example values above are illustrative, from the
FakeBackend's 80 ms per word.

### Settings and environment variables

| Variable | Default | Meaning |
| --- | --- | --- |
| `HEARNARRO_TTS_BACKEND` | `kokoro` if installed and pinned, else `fake` (with a warning) | `fake` or `kokoro` |
| `HEARNARRO_KOKORO_REVISION` | none | Hugging Face revision hash; required when the backend is `kokoro` |
| `HEARNARRO_LOOKAHEAD` | `5` | Segments kept ahead (SYN-5); integer ≥ 0 |
| `HEARNARRO_DATA_DIR` | `./data` | Root for the database, PDFs and audio (shared with M1) |
| `HEARNARRO_AUDIO_FORMAT` | `wav` (D16) | `opus` selects `OpusEncoder` (needs the `opus` extra) |
| `HEARNARRO_TEST_MODEL` | unset | `1` enables `@pytest.mark.model` tests |
| `HF_HOME` | Hub default | Where model weights are cached |

### Where offsets change space

There are two strings per segment (Technical Design "Segment model"):

- `text`: what the reader displays ("3.2%").
- `normalized_text`: what the TTS reads ("3.2 percent"), with
  `char_map: list[int]`, `len(char_map) == len(normalized_text)`, where `char_map[i]` is the index
  in `text` that normalized character `i` came from (`ingestion/normalize.py` → `normalize`:
  monotone, an expansion maps every output char inside the source token, a dropped citation
  emits nothing).

| Stage | Offset space |
| --- | --- |
| `TTSBackend.synthesize` output (`SynthResult.timestamps`) | `normalized_text` |
| `stretch.scale_timestamps` in and out | `normalized_text` (char offsets untouched) |
| **`SynthesisService` translation step (flow a, step 11)** | **normalized → text** |
| `AudioEntry.timestamps`, `audio_cache.timestamps_json`, `X-Timestamps` | `text` |
| Browser word spans (`data-start`/`data-end`, M3) | `text` |

Translation rule (the spec says only "translate through `Segment.char_map`"; this is the rule
`char_map`'s definition implies): a normalized span `[a, b)` with `b > a` becomes
`[char_map[a], char_map[b - 1] + 1)` in `text`. Because `char_map` is monotone, the result is
ordered and inside `text`; an expanded token ("percent" from "%") collapses onto its source
character. Words that come entirely from inserted text map onto their source token; neighbouring
words can map to the same text span, which the highlighter tolerates. `test_syn1_timestamps.py`
(tested) asserts the translated spans map into `text`.

## Concurrency model

There are three execution contexts in the one uvicorn process, plus M1's worker processes.

| Context | What runs there | May it block? |
| --- | --- | --- |
| asyncio event loop | Every HTTP handler (`async def`), the service's coroutines, queue bookkeeping, cache lookups via aiosqlite | No. Anything slow goes to a thread or a subprocess. |
| The synthesis thread (`ThreadPoolExecutor(max_workers=1, thread_name_prefix="synth")`) | `backend.synthesize`, `stretch_pcm`, `scale_timestamps`, in-process `encode` | Yes; that is its purpose. One job at a time. |
| Small `asyncio.to_thread` hops | Migrations at start-up, file reads/writes for cache files, executor shutdown | Yes, briefly. |
| M1 ingestion `ProcessPoolExecutor(max_workers=2)` | PDF parsing (`storage/jobs.py` → `run_ingestion`) | Yes; separate processes, separate GIL. |

**Why one synthesis thread.** The model's inference releases the GIL but competes for the same
CPU cores, so two concurrent syntheses on a laptop each run about half as fast and neither
finishes sooner (Technical Design D9). Serializing gives predictable latency: a request that jumps
the queue waits for at most the one job already running. A thread, not a process, so the loaded
model (hundreds of MB) is not duplicated and needs no pickling. A second backend on a GPU would
get its own executor.

**How the queue is consumed (code).** One `deque` of jobs (`segment`, `voice_id`, `speed`) shared by
all documents, bounded at 16 in total; seeks remove one document's jobs. One consumer coroutine per
service (started lazily on the first enqueue) pulls the next job,
checks the cache (skip if present), and awaits `run_in_executor(self._executor, job)`; because
the executor has one worker, at most one job runs at a time across all documents. A cache-miss
request does not enter the back of the queue; it is submitted ahead of the queued lookahead jobs.
An in-flight map from key to future lets a request for a key already being synthesized await
the same result.

**What a seek does to in-flight work.** Queued, not-started jobs for that document are dropped.
The running job cannot be interrupted (the backend call is a blocking C/Python call on another
thread); it completes and is cached. The new target jumps the queue and so starts as soon as the
running job ends. The worst-case added latency for a seek is therefore one synthesis.

**SQLite.** One aiosqlite connection per operation from `Engine.connect()`; WAL lets the
ingestion processes write while the API reads. Cache writes are small single-row inserts.

**Shutdown.** Cancel queue consumers and queued jobs, wait up to 5 s for the running job, then
shut the executor down without waiting (`cancel_futures=True`). Code as described; tested by
`test_syn5_shutdown_returns_within_5s_with_queue_full`.

## Speed handling

**Range and validation.** The API accepts 0.5 ≤ speed ≤ 3.0 in 0.1 steps (SYN-3); anything else
is 422 at the route. The value is canonicalized to one decimal before it reaches the service, so
cache keys compare equal.

**Native path.** `lo, hi = backend.speed_range()`; for `speed ≤ hi` the backend synthesizes at
`speed` directly (Kokoro applies speed in its duration predictor, so prosody stays natural). The
cache entry is keyed by that speed. Both `FakeBackend` and the designed `KokoroBackend` have
`(0.5, 2.0)`, and the API minimum equals `lo`, so no speed is below the native range.

**Stretched path.** For `speed > hi` (2.1 to 3.0): synthesize at `hi`, then
`stretch_pcm(pcm, sample_rate, ratio)` with `ratio = speed / hi` (1.05 to 1.5), and
`scale_timestamps(ts, ratio)`. The result is cached under the **requested** speed, so 2.5x is
one file and 3.0x another. The 2.0x intermediate is cached as its own entry too (spec amendment;
code: the stretched file is written first, then the native one if it is not cached yet). Stretch
always works from fresh PCM; a cached 2.0x file is not decoded and re-stretched (a later
optimisation, not needed for the gate).

**Timestamp scaling.** Code: `start_ms' = floor(start_ms / ratio + 1e-9)`, same for `end_ms`, then
clamped to the stretched `duration_ms` by the service; char offsets
are not touched (stretching changes time, not text). Since `1/ratio < 1`, order and
non-overlap are preserved; the test requires each value within 1 ms of the exact product.
The invariant "last `end_ms ≤ duration_ms`" after stretch depends on `stretch_pcm` returning
close to `len/ratio`; `test_syn1_timestamp_invariants_stretched_50_sentences` (tested) checks it at
2.5x and 3.0x (green, 297).

**Which tests pin it.** `test_syn3_speed.py` (green, 297): native path passes the speed straight to the
backend at 0.5/1.0/1.5/2.0; stretched path calls the backend at native max for 2.1/2.5/3.0;
scale math; stretch length; ratio bounds; API validation 0.5 to 3.0 in 0.1 steps.

## Dependencies and licences

**As built (phase 3, option A: vendor instead of `kokoro`).** `kokoro` on PyPI declares
`misaki[en]`, so any normal install pulls `phonemizer-fork` (GPL), `espeakng-loader` and
`num2words` (LGPL); pyproject cannot express "kokoro without its dependencies". The four model
files (`model.py`, `istftnet.py`, `modules.py`, `custom_stft.py`; 972 lines with headers) are
therefore vendored into `api/hearnarro/synthesis/kokoro_model/` with Kokoro's Apache-2.0 `LICENSE`
and a `NOTICE` listing the three changes (unused `attr` import dropped, so `attrs` is not needed;
relative import; stdlib logging instead of loguru). `g2p_en` is not a dependency either: its
distribution requires `distance` (GPL) and `nltk` (which downloads corpora at import), so only its
numpy GRU predictor and `checkpoint20.npz` (3.3 MB, unchanged) are vendored in
`api/hearnarro/synthesis/g2p_oov/` with `LICENSE` and `NOTICE`. The `tts` extra in
`api/pyproject.toml` is `torch`, `transformers`, `misaki==0.9.4` (no extras), `spacy>=3.8,<3.9`,
`en_core_web_sm` pinned by wheel URL (3.8.0), and `inflect` (MIT, backs `compat/num2words.py`);
`num2words` is removed from the base dependencies (`normalize.py` never used it), and
`kokoro-onnx`, `onnxruntime` and `soundfile` are gone. Install: `cd api && uv pip install -e
'.[dev,tts]'`. `scripts/check_licences.py` on that venv: 99 distributions, 0 violations
(`regex` is `Apache-2.0 AND CNRI-Python`; CNRI-Python, OSI-approved and permissive, was added to
the script's permissive set), and none of `kokoro`, `phonemizer`, `phonemizer-fork`, `espeakng-loader`,
`num2words`, `distance`, `nltk`, `g2p-en` installed (`_agent/results/310_install_licences.txt`).
`tests/test_licences.py` has no known violations left. The rest of this section is the
pre-build survey.

The project rule: every dependency and model in v1 is Apache-2.0, MIT or BSD (CLAUDE.md). The
state below is from the dependency survey (`_agent/results/253_m2_dependency_survey.md`, a
reading of package pages, no installs) and the Kokoro install spike
(`_agent/results/273_spike_install_and_licences.txt`, a scratch venv).

**Decided while this document was being written.** Commit `298ee2f` (after `9b68eb0`) added
"Amendments 2026-10-16 after the licensing spike" to `_agent/specs/m2-synthesis-interfaces.md`:

- **D15, Kokoro runtime without the GPL chain.** `kokoro` (Apache-2.0) on PyTorch CPU, model
  `hexgrad/Kokoro-82M` pinned at `f3ff3571791e39611d31c381e3a41a3af07b4987` and fetched with
  `hf_hub_download(revision=...)`. Never install `misaki[en]`, `phonemizer`, `phonemizer-fork`,
  `espeakng-loader`, `espeak-ng` or `num2words`. The backend builds its own pipeline over `KModel`
  + `misaki.en.G2P` so `kokoro.pipeline` is never imported; a shim module
  `hearnarro.synthesis.compat.num2words` (built in phase 3) is registered in
  `sys.modules` before misaki is imported; out-of-vocabulary words get a `g2p_en` (Apache-2.0)
  fallback with letter spelling last. Model and spaCy model load in the lifespan on the synthesis
  thread. The amendment also reports spike timings from results 273–279; this document has not
  opened those files and does not repeat the numbers.
- **D16, container.** `WavEncoder` is the M2 default. `OpusEncoder` via `opuscodec` (Apache-2.0,
  Ogg Opus) is optional behind `HEARNARRO_AUDIO_FORMAT=opus` and the `opus` extra (implemented, 333).
  No ffmpeg anywhere; Safari decode of Ogg Opus is checked in M3.
- **D17, stretch.** WSOLA in-process, ratio ≤ 1.5; D6's ffmpeg `atempo` is replaced. The spike
  used `audiotsm` (MIT); the shipped `stretch.py` is an own numpy WSOLA, so `audiotsm` is not a
  dependency.
- **Licence policy.** Non-copyleft OSI licences (PSF-2.0, ISC, MPL-2.0 at file level, BSL-1.0,
  Zlib, CC0, Unlicense) are acceptable for transitive components; copyleft and non-commercial
  terms stay excluded. A licence-check script is to move into `api/scripts/check_licences.py`.

The survey background below explains why those choices were made.

**Kokoro runtime.**

- `kokoro` 0.9.4 (Apache-2.0) runs the PyTorch model `hexgrad/Kokoro-82M` (Apache-2.0; survey
  read revision `f3ff3571791e39611d31c381e3a41a3af07b4987`). It exposes per-token
  `start_ts`/`end_ts`, which is what SYN-1 needs. It needs torch and transformers.
- `kokoro-onnx` 0.6.1 (MIT) runs ONNX weights with onnxruntime and no torch, but its tokenizer
  requires espeak-ng through `phonemizer`, and it exposes per-phoneme timings only (word timings
  would have to be aggregated by us).
- The Technical Design's "ONNX build" and single ONNX session assumption (D9) therefore meets a
  licence problem; the spike went the `kokoro` + torch route.

**The GPL phonemizer chain.** `kokoro` requires `misaki[en]`, whose extra pulls
`phonemizer-fork` (GPLv3+) and `espeakng-loader` (bundles espeak-ng, GPL-3; no licence metadata on
PyPI). The spike installed `kokoro==0.9.4` and base `misaki` with `--no-deps`, did **not** install
`phonemizer-fork`, `espeakng-loader` or `num2words` (LGPL), satisfied their imports with a shim
(`scripts/hn_shims.py` in the spike's scratch venv: a stub `misaki.espeak` and an own
`num2words`), and reports a licence table with `TOTAL 69 BAD [] UNKNOWN []` and all five excluded
packages absent. Whether synthesis quality and timestamps hold without the espeak fallback is
not measured here.

**Opus.** The survey found one permissive candidate with a macOS arm64 wheel: `opuscodec` 0.1.3
(Apache-2.0); whether it writes an Ogg container from Python was unverified. `soundfile` is BSD
but bundles LGPL libsndfile; PyAV is BSD but bundles LGPL-or-GPL FFmpeg. Browser side (survey,
secondary sources): WebM/Opus decodes in Safari from about 17.4, Ogg/Opus only from 18.4. The
spike file notes `opuscodec` and `audiotsm` were added in later spike steps (277, 278), whose
result files did not exist at read time.

**ffmpeg.** LGPL-2.1+ by default, GPL if built with GPL parts. D7 (Opus/WebM via an ffmpeg
subprocess) and D6 (`atempo`) both assumed it. The survey gives two readings of the licence rule
(strict: every executable we invoke must be permissive, ffmpeg fails; or ffmpeg as a separately
installed, unmodified tool is outside the rule). Undecided; the README's "ffmpeg must be on PATH"
line predates this.

**Time-stretch.** `audiotsm` 0.1.2 (MIT, numpy only, unmaintained since 2017) or a hand-written
WSOLA in numpy; ffmpeg `atempo` if ffmpeg is allowed. `librosa` 1.0 needs Python ≥ 3.12;
`pyrubberband` needs a GPL binary.

**Which module absorbs each decision.**

| Decision | Module that changes | What stays fixed |
| --- | --- | --- |
| `kokoro` vs `kokoro-onnx`, phonemizer, shims (D15: `kokoro` + own pipeline + `compat/num2words`) | `kokoro_backend.py`, `compat/` (and packaging) | `TTSBackend`; the service, routes and tests |
| Opus library vs ffmpeg vs WAV (D16: WAV default, `opuscodec` opt-in) | `encode.py` (`OpusEncoder`, `default_encoder`), `settings.py` | `AudioEncoder`; `media_type`/`ext` flow through the cache path and `Content-Type` |
| `atempo` vs WSOLA vs `audiotsm` (D17: `audiotsm`) | `stretch.py` | `stretch_pcm`/`scale_timestamps` signatures |

If an encoder or stretch implementation turns out to be a subprocess rather than in-process
code, it can be awaited with `asyncio.create_subprocess_exec` from the service instead of
running on the synthesis thread; the function signatures above are synchronous, so that would be
an interface change and would go through the spec first.

## Sentence boundaries

Synthesis is where a bad sentence split becomes audible (a pause in the middle of "Fig. 3"), so
the PRD's M2 bullet adds a boundary truth that is independent of the extractor.

**Truth files.** `api/tests/fixtures/pdfs/<stem>.sentences.txt`, one per text fixture (15: five
academic, five report, five tables). One reviewed sentence per line, prose block types only
(heading, body, list, caption, footnote; D12), in reading order. Each was derived from
`<stem>.expected.jsonl` by moving line breaks only: splitting two sentences on one line, joining
fragments at old block edges, rejoining splits after abbreviations (Eq., Fig., Natl., Inst.,
et seq., vs., e.g., i.e., No.) and a closing quote or bracket split onto its own line. The word
stream must stay identical to the expected file's.

**The metric** (`api/tests/boundary_util.py`, tested). A boundary is the word index after which
a sentence ends, over the D14 word stream (`tests.golden_util.words`):
`boundaries(sentences: list[str]) -> set[int]`. The parser's words are aligned to the truth's
with a word-level Levenshtein edit script (`_alignment`, common prefix and suffix trimmed first so
the quadratic table covers only the differing middle); an inserted parser word aligns to the
expected word before it, so it never shifts later boundaries.
`align_boundaries(actual_words: list[str], expected_words: list[str], actual_bounds: set[int], expected_bounds: set[int]) -> tuple[int, int, int]`
returns true positives, false positives, false negatives, and
`prf(tp: int, fp: int, fn: int) -> tuple[float, float, float]` gives precision, recall, F1
(0.0 on a zero denominator).

**The test** (`api/tests/test_syn_boundaries.py`). For each non-scanned fixture in
`manifest.json`: `test_ing5_syn1_boundary_truth_keeps_expected_word_stream` asserts the truth file
is non-empty, has no blank lines, and has exactly the expected file's word stream (the validator).
`test_ing5_syn1_boundary_measurement` and `test_ing5_syn1_boundary_measurement_table` run
`ingest(pdf, document_id=0, ocr=True)`, keep prose segments with the same filter as the M1 golden
(`prose_only`), and print per-fixture P/R/F1 and the mean. Run with `-s` to see the table.

**What the parser side computes.** The parser's sentences are M1's `Segment.text` values (pysbd
on merged block text, D4), so this measures M1's segmentation stage as it feeds synthesis.

**First measurement** (`_agent/results/261_boundary_measurement.txt`, 31 passed): mean over 15
fixtures P 0.8880, R 0.9849, F1 0.9332. Precision is the weak side: the parser splits more often
than the truth (for example `tables_01_pfn_bayes`: 141 parser sentences vs 118 truth, 25 false
positives). **No threshold is asserted.** The supervisor sets the thresholds after this first
measurement; until then the test only prints.

## How to run

All commands from `api/` with the project venv (`.venv`, Python 3.11).

```bash
cd api

# All tests (FakeBackend only; @model tests skip unless HEARNARRO_TEST_MODEL=1)
.venv/bin/python -m pytest

# The M2 unit tests that pass today (32 passed at read time, result 281)
.venv/bin/python -m pytest tests/test_fake_backend.py tests/test_encode.py \
    tests/test_settings.py tests/test_boundary_util.py -q

# M2 tests by requirement
.venv/bin/python -m pytest tests/test_syn1_timestamps.py tests/test_syn3_speed.py -q

# Sentence-boundary measurement with the printed table
.venv/bin/python -m pytest tests/test_syn_boundaries.py -s -q

# Lint and format
.venv/bin/ruff check . && .venv/bin/ruff format --check .
```

Model smoke and gate (needs the `tts` extra; the revision defaults to the D15 pin):

```bash
HEARNARRO_TEST_MODEL=1 HEARNARRO_KOKORO_REVISION=<hash> \
    .venv/bin/python -m pytest -m model -s
```

Benchmark (`HF_HOME` is where the 327 MB model is cached):

```bash
HEARNARRO_TTS_BACKEND=kokoro HEARNARRO_KOKORO_REVISION=<hash> \
    .venv/bin/python scripts/bench.py        # prints a table, writes bench/<date>.json
```

Server:

```bash
# With the fake backend (silent audio, exact timing; no model needed)
HEARNARRO_TTS_BACKEND=fake .venv/bin/python -m hearnarro serve --data-dir ~/hearnarro-m2 --port 8765

# With Kokoro (tts extra installed; the revision defaults to the D15 pin)
HEARNARRO_TTS_BACKEND=kokoro HEARNARRO_KOKORO_REVISION=<hash> HF_HOME=~/.cache/huggingface \
    .venv/bin/python -m hearnarro serve --data-dir ~/hearnarro-m2 --port 8765

# Then (the full procedure with expected output is docs/M2_TESTING.md)
.venv/bin/python scripts/m1_smoke.py --base-url http://127.0.0.1:8765 --audio
curl -s http://127.0.0.1:8765/voices
curl -sI "http://127.0.0.1:8765/audio/1?voice=fake_f1&speed=1.0"           # 404 before first GET
curl -s -D - -o seg1.wav "http://127.0.0.1:8765/audio/1?voice=fake_f1&speed=1.0"
```

`serve` is M1's CLI (`hearnarro/cli.py`); it passes only `--data-dir`, so backend, revision and
lookahead come from the environment through `load_settings()`.

## Open items

| Item | Where | Lands in |
| --- | --- | --- |
| `SynthesisService` (`get_audio`, `prefetch`, `queue_depth`, real `shutdown`), `DbSegmentRepo` | `service.py` | done, phase 2 |
| `AudioCache` (`get`, `put`, `mark_failed`); `document_id` lookup for the file path; `media_type` from extension | `cache.py` | done, phase 2 |
| `stretch_pcm`, `scale_timestamps` (numpy WSOLA, D17) | `stretch.py` | done, phase 2 |
| `GET`/`HEAD /audio`, `GET /voices` | `routes/audio.py`, `routes/voices.py` | done, phase 2 |
| `test_syn5_queue.py`, `test_api_audio.py`, `test_syn_gate.py` (FakeBackend part) | `api/tests/` | done (written before the code) |
| `OpusEncoder` (`opuscodec`, Ogg; D16) | `encode.py` | done, phase 4 (333) |
| `KokoroBackend`, the `@model` smoke and gate tests, the skip hook for `HEARNARRO_TEST_MODEL` | `kokoro_backend.py`, `conftest.py`, `test_syn_gate.py` | done, phase 3 (311) |
| Model load on the synthesis thread before `yield` in the lifespan | `app.py` | done, phase 2 (`build_backend` runs on `synth_executor`) |
| 5 s cap on shutdown | `service.py`, `app.py` | done, phase 2 |
| `scripts/bench.py`; first TTFA and RTF numbers | `api/scripts/` | done, phase 3 (314: at 0.5x 6 of 20 sentences of up to 200 chars exceed 2 s) |
| Boundary thresholds asserted in `test_syn_boundaries.py` | `api/tests/` | done (D18) |
| Retry policy for a key whose row is `failed` (retry vs 502 from the row) | `service.py` | done: retried once, then 502 from the row |
| Exact seek rule ("outside the window") | `service.py`, `test_syn5_queue.py` | done: outside `[last, last+N]` or a voice/speed change |
| Whether the native-max intermediate is cached for the stretched path, and whether stretch works from PCM or a decoded cache file | `service.py` | done: both cached; stretch from fresh PCM |
| `test_syn5_seek_clears_queue_and_refills_from_new_position` and `test_syn5_first_request_jumps_the_queue` compare by `normalized_text`, but report_01 orders 0 and 4 (and 1 and 5) have the same text, so the explicitly requested order 0 matches `at(4)`; the service synthesized orders 0, 30..34 and 0, 40 (`_agent/results/299_queue_test_text_collision.txt`). Fix: compare by segment id or order | `api/tests/test_syn5_queue.py` | done (commit 5350b46) |
| Header-size limit for `X-Timestamps` on long sentences (sidecar JSON is the PRD's alternative) | `routes/audio.py` | measure in phase 2 |
| Deleting a document's audio files (rows cascade; files do not) | LIB-4 | M4 |
| PRD SYN-6 says "keyed by (segment hash, voice, speed)"; the design and DDL key by `segment_id` and backend | `docs/PRD.md` | done, phase 4 (SYN-6 row reads "segment id") |
| `hearnarro/synthesis/compat/num2words`, `HEARNARRO_AUDIO_FORMAT` in settings, `api/scripts/check_licences.py` (D15, D16, spec amendment) | `synthesis/compat/`, `settings.py`, `api/scripts/` | done, phase 3 |
| Technical Design D9 assumes an ONNX session; D15 uses `kokoro` + torch | `docs/TECHNICAL_DESIGN.md` | done (D9 reads "model session (PyTorch CPU, D15)") |
