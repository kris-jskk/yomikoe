# M2 synthesis interfaces (supervisor-owned)

Source of truth for algorithms: `docs/TECHNICAL_DESIGN.md` "Synthesis service", "Audio delivery and
playback (D5)", "Storage (D7)" (audio_cache DDL), "Concurrency and process model (D9)"; requirements
SYN-1..SYN-6 in `docs/PRD.md`. Gate (PRD M2): first audio in 2 s at 0.5x–3x on CPU. Package root
`api/hearnarro/synthesis/`. Tests are written against this file before the code exists.

## backend.py (exists; unchanged)
`TTSBackend` Protocol (`name`, `voices()`, `speed_range()`, `synthesize(text, voice_id, speed) -> SynthResult`),
`Voice`, `WordTimestamp(word, start_ms, end_ms, char_start, char_end)` (offsets into the text passed in),
`SynthResult(audio: bytes PCM16 mono, sample_rate, timestamps)`.

## fake.py — FakeBackend (every test except the @model smoke uses it)
```python
class FakeBackend:
    name = "fake"
    def voices(self) -> list[Voice]        # 6 voices: fake_f1..f3 (female), fake_m1..m3 (male), language "en-US"
    def speed_range(self) -> tuple[float, float]   # (0.5, 2.0)
    def synthesize(self, text, voice_id, speed) -> SynthResult
        # 24_000 Hz; per whitespace-separated word: 80 ms of silence / speed, words back to back,
        # timestamps evenly spaced, char_start/char_end = the word's span in `text`; deterministic;
        # unknown voice_id -> ValueError; empty text -> SynthResult with 0 bytes and [] timestamps
```

## stretch.py — speeds above the backend's native range (D6)
```python
def stretch_pcm(pcm: bytes, sample_rate: int, ratio: float) -> bytes      # ratio = requested / native_max, 1.0 < ratio <= 1.5; output length ≈ len/ratio
def scale_timestamps(ts: list[WordTimestamp], ratio: float) -> list[WordTimestamp]   # start/end * (1/ratio), ints, order preserved, char offsets untouched
```
Implementation chosen by the M2 survey (ffmpeg `atempo` subprocess if a permissively usable ffmpeg
exists; otherwise a numpy WSOLA in-process). The interface does not change either way.

## encode.py — container for the browser (D7)
```python
class AudioEncoder(Protocol):
    media_type: str; ext: str
    def encode(self, pcm: bytes, sample_rate: int) -> bytes
class WavEncoder      # media_type "audio/wav", ext "wav"; stdlib `wave`; always available (fallback and tests)
class OpusEncoder     # media_type "audio/webm" or "audio/ogg", ext accordingly; chosen by the survey; raises EncoderUnavailable if its dependency is missing
def default_encoder() -> AudioEncoder   # Opus when available else Wav; logged once
```

## cache.py — AudioCache (write-through; D7)
```python
@dataclass
class AudioEntry: segment_id: int; voice_id: str; speed: float; backend: str; status: str; path: Path | None; media_type: str; duration_ms: int; timestamps: list[WordTimestamp]   # timestamps in TEXT offsets
class AudioCache:
    def __init__(self, data_dir: Path, db)            # files: data_dir/audio/{document_id}/{segment_id}/{voice_id}_{speed:.1f}.{ext}
    async def get(self, segment_id, voice_id, speed, backend) -> AudioEntry | None
    async def put(self, entry, audio_bytes) -> AudioEntry   # write path+".tmp", rename, then insert row (status ready)
    async def mark_failed(self, segment_id, voice_id, speed, backend, reason)
```
Rows live in `audio_cache` exactly as the D7 DDL defines (primary key segment_id, voice_id, speed, backend).

## service.py — SynthesisService (SYN-1, SYN-3, SYN-5, SYN-6)
```python
class SegmentSynthesisFailed(Exception): ...
class SynthesisService:
    def __init__(self, backend: TTSBackend, encoder: AudioEncoder, cache: AudioCache, repo, *, lookahead: int = 5, executor: ThreadPoolExecutor | None = None)   # executor max_workers=1 (D9)
    async def get_audio(self, segment_id: int, voice_id: str, speed: float) -> AudioEntry
        # cache hit -> return; miss -> this job jumps the queue, runs synthesize(+stretch)(+encode) on the executor,
        # cache.put, then enqueue lookahead segment_id+1 .. +lookahead for the same (document, voice, speed)
        # timestamps: backend offsets are into normalized_text; translate through Segment.char_map to `text` offsets before caching
        # speed <= native max: native; else synthesize at native max, stretch by requested/native_max, scale timestamps
    async def prefetch(self, document_id: int, from_order: int, voice_id: str, speed: float) -> None   # clear queue for the document, refill from from_order
    def queue_depth(self, document_id) -> int
    async def shutdown(self)   # cancel queue, wait ≤ 5 s for in-flight
```
Speed validation lives in the API: 0.5 ≤ speed ≤ 3.0 and speed*10 integral → else 422.

## routes/audio.py and routes/voices.py (PRD "REST endpoints")
- `GET /audio/{segment_id}?voice=&speed=` → 200 body = encoded audio, `Content-Type` = encoder media type,
  `X-Timestamps` = JSON list of {word,start_ms,end_ms,char_start,char_end} (text offsets), `X-Duration-Ms`.
  Cache miss blocks until synthesized. 404 unknown segment; 422 bad speed/voice; 502 JSON {segment_id, reason} when synthesis fails (row marked failed).
- `HEAD /audio/{segment_id}?voice=&speed=` → 200 if cached ready, 404 otherwise (never synthesizes).
- `GET /voices` → list of Voice across registered backends.
- `GET /documents/{id}` and the list gain nothing new in M2.

## config
`settings.py`: HEARNARRO_TTS_BACKEND (fake|kokoro, default kokoro when available else fake with a warning),
HEARNARRO_KOKORO_REVISION (pinned hash, required when kokoro), HEARNARRO_LOOKAHEAD (5), HEARNARRO_DATA_DIR.

## kokoro_backend.py — the only module that names a model
Package and phonemizer chosen by the M2 survey (licence: Apache/MIT/BSD end to end, model Apache-2.0,
revision pinned). `KokoroBackend(revision=...)`. One smoke test `@pytest.mark.model`, skipped unless
`HEARNARRO_TEST_MODEL=1`: synthesize one sentence, assert audio > 0.3 s and timestamps non-empty.

## scripts/bench.py (PRD M2)
Time-to-first-audio and real-time factor for the configured backend over 20 sentences from the fixtures
(cold cache, warm model), speeds 0.5/1.0/2.0/3.0; prints a table; writes `bench/<date>.json`.

## Tests (D11), written first
- `test_syn1_timestamps.py`: for 50 fixture sentences through FakeBackend + service: sorted, non-overlapping,
  last end_ms ≤ duration_ms, every (char_start,char_end) maps into `text`; after stretch the same invariants hold.
- `test_syn3_speed.py`: native vs stretched path; scale_timestamps math; 0.5..3.0 step validation.
- `test_syn5_queue.py`: lookahead enqueues N; seek clears/refills; cached jobs skipped; first request jumps the queue.
- `test_api_audio.py`: contract via httpx against a temp data dir with FakeBackend: miss then hit (second call faster and
  HEAD 200), headers, 404/422/502, /voices has ≥ 6 voices across both genders (SYN-2).
- `test_syn_gate.py`: FakeBackend contract version always; Kokoro version @model: TTFA ≤ 2000 ms at 0.5/1.0/2.0/3.0 on a 150-char sentence.

## Sentence-boundary truth and metric (deferred from M1; PRD M2 bullet)
- Files: `api/tests/fixtures/pdfs/<stem>.sentences.txt`, one sentence per line, prose types only
  (heading/body/list/caption/footnote), reading order, words as the golden tokenizes them. Derived from
  `<stem>.expected.jsonl` by a reviewer who fixes the known-bad boundaries: splits after abbreviations
  (Eq., Fig., Natl., Inst., et seq., vs., e.g., i.e., No.), fragments at old block edges, a closing quote or
  bracket split into its own line, two sentences in one line. The word stream must stay identical to the
  expected file's (only line breaks move); a validator asserts this.
- Metric (`api/tests/boundary_util.py`): a boundary is the word index after which a sentence ends; align the
  parser's word stream to the truth's with the word-level edit script; precision, recall and F1 of parser
  boundaries vs truth. Test prints per fixture; thresholds are set by the supervisor after the first
  measurement (not asserted until then).

## Amendments 2026-10-16 after the licensing spike (results 273–279)

**D15 — Kokoro runtime without the GPL chain.** `kokoro` (Apache-2.0) on PyTorch CPU; model
`hexgrad/Kokoro-82M` pinned at f3ff3571791e39611d31c381e3a41a3af07b4987 and fetched with
`hf_hub_download(revision=...)` (KModel's own download ignores the revision). Never install
`misaki[en]`, `phonemizer`, `phonemizer-fork`, `espeakng-loader`, `espeak-ng` or `num2words`.
The backend builds its own pipeline over `KModel` + `misaki.en.G2P` so `kokoro.pipeline` (which
imports `misaki.espeak`, hence phonemizer) is never imported. `misaki.en` imports `num2words`
(LGPL) at module top level: the backend registers `hearnarro.synthesis.compat.num2words` (our
own, MIT-compatible, number-to-words via `inflect`) in `sys.modules` before importing misaki;
this is documented as a shim in the code map. Out-of-vocabulary words: misaki drops them silently
(result 274), so the backend adds a fallback G2P: `g2p_en` (Apache-2.0) ARPAbet → IPA mapped
into Kokoro's vocabulary, letter spelling only as the last resort; a warning is logged per OOV
word. Model and spaCy model load in the lifespan on the synthesis thread (cold start ≈ 2 s;
warm first audio ≈ 0.8 s on this machine, RTF 0.078). `kokoro` needs `attrs` (undeclared): pin it.
Measured speed input: 0.5/1.0/2.0 → 11.55/5.75/3.33 s of audio for the same sentence.

**D16 — Container.** M2 ships `WavEncoder` as default (stdlib, decodes everywhere). `OpusEncoder`
via `opuscodec` (Apache-2.0; Ogg Opus, QEXT off, ≈ 7x smaller) is available behind
`HEARNARRO_AUDIO_FORMAT=opus`. Browser decode of Ogg Opus (Safari before 18.4 reportedly fails) is
verified in M3 with the real player; a WebM muxer is written only if Safari needs it. D7 in the
Technical Design is amended accordingly; no ffmpeg anywhere.

**D17 — Stretch.** `audiotsm` (MIT, numpy) WSOLA in-process, ratio ≤ 1.5 (measured: −1.5 % length
error, ≈ 20 ms). D6's ffmpeg atempo is replaced.

**Licence policy clarification (CLAUDE.md).** Transitive components under other OSI-approved,
non-copyleft licences (PSF-2.0, ISC, MPL-2.0 at file level, BSL-1.0, Zlib, CC0, Unlicense) are
acceptable; copyleft (GPL, LGPL, AGPL, SSPL) and non-commercial terms remain excluded. Every
install is checked with the licence script from the spike (`lic_check.py`, to be moved into
`api/scripts/check_licences.py` and run in the test suite).

## Amendments 2026-10-16 from the code-map review (docs/CODE_MAP_M2.md "Open items")

- `AudioEntry` gains `document_id: int` (needed for the cache file path); `AudioCache.get/put` take it from the segment row.
- `media_type` is not a column: it is derived from the cached file's extension (`.wav` → audio/wav, `.opus`/`.ogg` → audio/ogg); `AudioEntry.media_type` is filled at read time.
- Failed rows: a `failed` row is retried once on the next explicit `GET` for that key (not by the lookahead queue); a second failure keeps the row failed until a `DELETE` of the document or a manual cache clear. The retry count lives in `timestamps_json` as `{"failures": n}` to avoid a migration.
- Seek detection: the service tracks, per (document_id, voice_id, speed), the last requested order; a `GET` whose order is outside `[last, last + lookahead]` is a seek: clear that document's queue and refill from the new order. `prefetch()` is the explicit form the client may call.
- Stretch path caches both the native 2.0x file and the stretched file (as D6 says).
- `app.py`: the backend is constructed on the synthesis thread (`run_in_executor`) during lifespan so the model load never blocks the event loop; shutdown waits ≤ 5 s for the in-flight job, then cancels.
- PRD SYN-6 wording "segment hash" is read as "segment id" (D7 rationale); the PRD row is updated when M2 closes. Technical Design D9's "ONNX session" wording becomes "model session (PyTorch CPU, D15)" in the same update.
