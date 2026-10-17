# PRD: HearNarro

As of 2026-10-15 · Sowmya

## Overview

HearNarro is a Speechify-style reader: drop in a PDF, pick a voice and a speed, and listen with the text highlighted as it plays. v1 is a self-hosted web app backed by open TTS models, built so the synthesis engine can be swapped without touching the reader.

The problem it solves: long documents (papers, reports, textbooks) are easier to consume as audio while walking, driving or doing chores, but generic PDF-to-audio tools mangle layout, read footnotes mid-sentence, and sound flat. Commercial products (Speechify, Natural Reader) solve this well but are subscription-gated, closed, and run on their own voices.

Vision in one line: an open, extensible reading engine where the hard part is text extraction and playback plumbing, and the voice is a pluggable backend.

## Goals, non-goals and success metrics

v1 ships a working reader for born-digital and scanned PDFs with at least 6 voices and speeds from 0.5x to 3x, running locally on a laptop with no GPU.

**Goals**

- Read any PDF end to end in correct reading order, skipping headers, footers and page numbers
- Playback starts within 2 seconds of pressing play on a 50-page document
- Word-level highlighting synced to audio
- Voice and speed can be changed mid-document without losing position
- Synthesis backend is an interface; Kokoro is the first implementation, a GPU model the second
- Library persists documents, reading position and settings across sessions

**Non-goals for v1**

- Voice cloning or custom voice training
- Mobile native apps (web app must work on a phone browser, that is enough)
- Summaries, chat-with-PDF, mind maps
- Multi-user accounts, sharing, billing
- Non-PDF formats (EPUB, DOCX, web pages); keep the ingestion interface open for them

**Success metrics**

| Metric | Target | How measured |
| --- | --- | --- |
| Reading-order accuracy on a 20-PDF test set | 95% of sentences in correct order | Manual review against ground truth |
| Time to first audio (50-page PDF, CPU) | < 2 s | Instrumented in the API |
| Real-time factor, Kokoro on CPU | < 0.3 (3x faster than playback) | Benchmark script |
| Highlight drift after 10 minutes of playback | < 1 word | Manual check on 5 documents |
| Crash-free playback of a 300-page PDF | 100% | Soak test |

Evals (EVAL-1 to EVAL-9, decided 2026-10-17; Technical Design D31–D34) produce the trend line for these metrics and for quality the gates do not measure: every run keeps its per-example scores in a committed record so two commits can be compared. The gate tests remain the floor and the only thing that blocks a merge.

## Users and use cases

The first user is you: a technical reader working through long papers and reports who wants to listen while away from the screen. Design for that person first; the other personas below shape the interface but do not gate v1.

| Persona | Core need | What they do in the app |
| --- | --- | --- |
| Technical reader (primary) | Get through a 40-page paper on a walk | Upload, pick a voice, play at 1.5–2x, skip the references section |
| Student | Study a scanned textbook chapter | Upload a photographed PDF, rely on OCR, follow the highlight while listening |
| Accessibility user (dyslexia, low vision) | Read any document comfortably | Larger highlight, slower speed, keyboard-only control |
| Commuter | Hands-free listening | Resume where they left off, background playback on phone browser |

**Core flows**

1. Upload a PDF, see it parsed into sections within seconds, press play.
2. Change voice or speed mid-sentence; playback continues from the same word.
3. Tap any sentence in the reader to jump there.
4. Close the tab, come back tomorrow, resume from the exact position.
5. Skip a block (figure caption, references, footnotes) with one action.

## Functional requirements

Requirements are tagged P0 (v1 must have), P1 (v1 should have), P2 (later). IDs are stable so the coding session can reference them in commits and tests.

**Ingestion (ING)**

| ID | Pri | Requirement |
| --- | --- | --- |
| ING-1 | P0 | Accept PDF upload up to 100 MB via drag-drop or file picker |
| ING-2 | P0 | Detect per page whether a text layer exists; run OCR only on pages without one |
| ING-3 | P0 | Extract text as structured blocks with type: heading, body, caption, footnote, header/footer, table, equation, list item; figure-internal text is typed figure and never read (D12) |
| ING-4 | P0 | Produce a linear reading order that handles two-column layouts and excludes header/footer/page-number blocks |
| ING-5 | P0 | Join hyphenated line breaks and merge lines into sentences; split into sentence-level segments with character offsets back to the source block. A bulleted or numbered list item (any common bullet glyph, arrows included) is its own segment, never joined with the next item into one sentence; a glyph bullet is shown but not spoken |
| ING-6 | P1 | Normalize text for speech: numbers, currency, dates, URLs → domain spoken with dot ("shopping dot com", e-mail "name at host dot com"), citations like \[12\], common abbreviations; acronym pronunciation decided in the backend with a lexicon and overrides, in context: a collocation ("TED talk") or the document's own definition ("Transferable Erosion Deposit (TED)", stored per document at ingestion) changes the reading |
| ING-7 | P1 | Tables read as row-by-row prose with a spoken cue ("Table 2, 3 rows"); equations read as a cue ("equation") not symbol soup |
| ING-8 | P1 | Build a table of contents from headings for navigation |
| ING-9 | P2 | Ingestion interface accepts EPUB, DOCX, HTML through the same block schema |

**Synthesis (SYN)**

| ID | Pri | Requirement |
| --- | --- | --- |
| SYN-1 | P0 | Synthesize one sentence segment at a time and return audio plus word-level timestamps |
| SYN-2 | P0 | At least 6 distinct voices across both genders with a language tag; voice list exposed via API |
| SYN-3 | P0 | Speed from 0.5x to 3.0x in 0.05 steps (so 1.25x and 1.75x are valid); applied in the model's duration control where supported, time-stretch fallback above the model's range |
| SYN-4 | P0 | Backend is an interface (`synthesize(text, voice, speed) -> audio, timestamps`); Kokoro is the first implementation |
| SYN-5 | P0 | Lookahead queue: keep N segments ahead of playback synthesized; N configurable, default 5 |
| SYN-6 | P1 | Cache synthesized audio keyed by (segment id, voice, speed) so re-listening is instant; the id, not a text hash, so a re-ingested document never reuses stale audio (D7) |
| SYN-7 | P1 | Second backend (GPU model such as Fish Speech or Qwen3-TTS) selectable per document |
| SYN-8 | P2 | Content-aware delivery: pause length and pitch differ for headings, captions, body text |
| SYN-9 | P2 | Voice cloning from a reference clip |

**Playback (PLAY)**

| ID | Pri | Requirement |
| --- | --- | --- |
| PLAY-1 | P0 | Play, pause, skip forward/back one sentence, skip to next/previous section |
| PLAY-2 | P0 | Current word and sentence highlighted in the text view in sync with audio |
| PLAY-3 | P0 | Click any sentence to seek there |
| PLAY-4 | P0 | Changing voice or speed mid-playback resumes at the current sentence, flushes the lookahead queue |
| PLAY-5 | P0 | Gapless stitching between segments; no audible click at boundaries |
| PLAY-6 | P1 | Keyboard shortcuts: space, left/right arrows, +/- for speed |
| PLAY-7 | P1 | Media Session API so lock-screen controls work on phone browsers |
| PLAY-8 | P1 | Skip-block toggles: mute footnotes, captions, references section |
| PLAY-9 | P2 | Export whole document as MP3 or M4B with chapter markers |

**Library (LIB)**

| ID | Pri | Requirement |
| --- | --- | --- |
| LIB-1 | P0 | List of uploaded documents with title, page count, progress percent, last opened |
| LIB-2 | P0 | Reading position (segment id + offset) saved every 5 seconds and on pause |
| LIB-3 | P0 | Per-document voice and speed remembered; a global default for new documents |
| LIB-4 | P1 | Delete a document and its cached audio |
| LIB-5 | P2 | Folders or tags |

**Evals (EVAL)**

Added 2026-10-17 (Technical Design D31–D34). An eval runs the system over a fixed dataset, scores every example and records the scores against the commit; it has no threshold and never fails a build. Tier 0 needs no model (seconds), tier 1 needs Kokoro or another tool on CPU (minutes, on demand), tier 2 is a human session. The ING/SYN/PLAY/LIB IDs in parentheses are what each eval measures.

| ID | Requirement | Dataset | Scorer | Tier |
| --- | --- | --- | --- | --- |
| EVAL-1 | Reading order: is the prose in the right order? (ING-3, ING-4, ING-5) | 20 fixture PDFs, `*.expected.jsonl` | Word-sequence edit-distance score (D14) plus char-mass guard; mean, min, per class | 0 |
| EVAL-2 | Sentence boundaries: are sentences split where a reader would pause? (ING-5, SYN-1) | 15 `*.sentences.txt` | Boundary precision, recall, F1 (D18); mean F1, min recall | 0 |
| EVAL-3 | Clean text: how much junk reaches the voice? (ING-1 to ING-6) | Same 15 fixtures | Quality checklist counts per 1 000 words, per check and total | 0 |
| EVAL-4 | Speech form: does the text sent to the voice read aloud correctly? (ING-6, ING-7, SYN-4) | `evals/data/speech_form.jsonl`, ~300 raw → spoken pairs (numbers, dates, units, ordinals, abbreviations, acronyms, table and equation cues) | Exact match on the spoken string, word edit distance as partial credit; accuracy per category | 0 |
| EVAL-5 | Intelligibility: can the audio be understood? (SYN-1, SYN-4) | 50 fixture sentences | Round trip TTS → ASR (Whisper, MIT, dev-only) → word error rate vs the normalized input; mean, worst, per voice | 1 |
| EVAL-6 | Sync: do the word timestamps match the audio? (SYN-1, PLAY-3) | Same 50 sentences | ASR word timings vs backend timestamps: mean absolute offset (ms), p95, share within 150 ms, per speed 0.5/1/2/3x | 1 |
| EVAL-7 | Speed: how fast is synthesis on this machine? (SYN-5) | 20 bench sentences | `bench.py` time-to-first-audio p50/p95 and real-time factor | 1 |
| EVAL-8 | OCR: how accurate is the scanned path? (ING-2) | 5 scanned fixtures | Character error rate vs expected text; mean, max | 1 |
| EVAL-9 | Listening: does it sound good to a person? | 10 sentences × 2 voices | 1–5 rubric (naturalness, pronunciation errors counted, pacing) filled by a human; mean per voice, error count | 2 |

## Architecture and stack

```
Reader (browser)
  text view + word highlighting, Web Audio scheduled playback, keyboard + lock-screen controls
  reads segments over REST; fetches audio one segment at a time over HTTP
        |  REST
API server (FastAPI)
  REST: upload, documents, segments, voices, reading position, /audio/{segment_id}
  keeps a 5-segment lookahead queue per active document
   |  parse job            |  synthesize(segment, voice, speed)     |  read / write
Ingestion worker          Synthesis service  --cache-->           Storage
  pdfplumber text, OCR      TTSBackend interface                    SQLite: docs, segments, state
  blocks, order, sentences  Kokoro now, GPU backend later           files: PDFs, WAV/Opus cache
  async job per upload      audio + word timestamps out             cache key: segment, voice, speed
  \-- writes parsed segments -----------------------------------------^
```

The browser never touches a model or the PDF; it asks the API for parsed segments and fetches audio one segment at a time over HTTP, scheduling each decoded buffer back to back with the Web Audio API. Ingestion runs once per upload and writes segments to storage; synthesis runs on demand per segment, caches its output, and is the only place a TTS model is named.

**Stack decisions**

| Layer | Choice | Why |
| --- | --- | --- |
| Language | Python 3.11+ | Every TTS and PDF library of note is Python-first |
| API | FastAPI + uvicorn | Async, typed schemas for free |
| PDF text | pdfplumber (MIT; pdfminer.six) + pypdfium2 (Apache-2.0/BSD-3) for OCR rendering | Glyph coordinates, fonts, drawings and tables for layout analysis under a permissive license; replaced PyMuPDF (AGPL-3.0) in M1 (D13) |
| Layout / academic PDFs | Marker (optional, P1) | Handles two-column papers and equations better than a raw geometric parser |
| OCR | Tesseract via pytesseract, PaddleOCR as upgrade | Tesseract is zero-setup; Paddle is more accurate on photos |
| Sentence split | pysbd | Rule-based, handles abbreviations and citations better than regex |
| Text normalization | Custom rules | No off-the-shelf library covers citations and tech vocabulary; `num2words` (LGPL) is not used (D15) |
| TTS v1 | Kokoro-82M via vendored model code on PyTorch CPU, GPL-free (D15) | Apache-2.0, \~50 voices (10 exposed in v1), native speed parameter, word timings from predicted durations; the `kokoro` package is not installed because its `misaki[en]` extras are GPL/LGPL |
| TTS v2 | Fish Speech or Qwen3-TTS behind the same interface | Higher quality, needs a GPU |
| Time-stretch fallback | WSOLA in process (D17) | Only above the model's native speed range (2.05–3.0x); numpy, no extra dependency, pitch kept |
| Audio format | PCM 24 kHz internally; WAV per segment by default, Ogg Opus optional (D16); browser matrix run in M3: both decode on Chromium, WebKit and Firefox under Playwright; WAV stays the default until one play in the user's own Safari (M4 item, user decision 2026-10-17; Ogg Opus decodes on Chromium, WebKit and Firefox, `_agent/results/421`–`423`) | WAV needs no dependency and decodes everywhere via decodeAudioData; Ogg Opus at 48 kbps (`opuscodec`, Apache-2.0, `opus` extra) is 6–8x smaller (42 KB vs 276 KB for a 5.75 s sentence) |
| Storage | SQLite + local filesystem | Single-user v1; swap to Postgres + S3 when multi-user |
| Job queue | In-process asyncio task queue | No Redis until there is more than one worker |
| Frontend | React + TypeScript, Vite | Web Audio API scheduled buffers for gapless playback (decided 2026-10-15, see Technical Design D5), Media Session API |
| Packaging | Docker Compose | One command to run API, worker and web |
| Tests | pytest, a fixture set of 20 PDFs | Reading-order and timestamp regressions are the main risk |

**Hugging Face models**

Every model in v1 is downloaded from the Hugging Face Hub; nothing is trained in-house. The exact repo ids below should be verified on the Hub before pinning, and each one is pinned to a revision hash in config so a Hub update cannot silently change audio or timestamps.

| Role | Hub repo (verify) | License | How it loads |
| --- | --- | --- | --- |
| TTS v1 | `hexgrad/Kokoro-82M`, pinned at revision `f3ff3571791e39611d31c381e3a41a3af07b4987` | Apache-2.0 | `hf_hub_download(revision=...)`; vendored model code on PyTorch CPU (D15) |
| TTS v2 (GPU) | `fishaudio/fish-speech-*` or `Qwen/Qwen3-TTS-*` | Apache-2.0 | Model's own inference code or `transformers` |
| OCR, scanned pages (HF-only option) | `microsoft/trocr-base-printed`, `facebook/nougat-base` for academic layouts | MIT / CC-BY-NC (Nougat, check) | `transformers`; Tesseract stays the default because it needs no GPU |
| Layout analysis | Marker's bundled detection and layout models | GPL-3 (Marker) | `marker-pdf` package; optional, P1 |
| Benchmark-only | `coqui/XTTS-v2`, `suno/bark` | Non-commercial / MIT | Quality reference, never shipped |

Two ways to run any of these, both behind the same `TTSBackend` interface: locally via `huggingface_hub` downloads (v1 default, offline), or through a Hugging Face Inference Endpoint over HTTPS as a `RemoteBackend` (the cheapest way to audition a GPU model before self-hosting). In Docker Compose, `HF_HOME` points at a named volume so downloads survive rebuilds.

## Data model and API

Three tables carry the whole product: a document, its ordered segments, and the audio cache. Everything the reader shows or plays is addressed by `segment_id`.

**Tables**

| Table | Key columns | Notes |
| --- | --- | --- |
| documents | id, title, filename, page\_count, status (uploaded, parsing, ready, failed), created\_at, voice\_id, speed, position\_segment\_id, position\_offset\_ms | One row per upload; voice and speed are the per-document settings |
| blocks | id, document\_id, page, order, type (heading, body, caption, footnote, header, table, equation, list), bbox, raw\_text | Output of layout analysis; kept for debugging and future re-segmentation |
| segments | id, document\_id, block\_id, order, text, normalized\_text, char\_start, char\_end, section\_id | One sentence each; `order` is the reading order; `normalized_text` is what the TTS reads |
| sections | id, document\_id, title, level, first\_segment\_id | Table of contents from headings |
| audio\_cache | segment\_id, voice\_id, speed, backend, path, duration\_ms, timestamps\_json, created\_at | Primary key (segment\_id, voice\_id, speed, backend) |
| voices | id, name, backend, language, gender, sample\_path | Seeded from each backend's catalog on startup |

**TTS backend interface**

```python
class TTSBackend(Protocol):
    name: str
    def voices(self) -> list[Voice]: ...
    def speed_range(self) -> tuple[float, float]: ...   # native range, e.g. (0.5, 2.0) for Kokoro
    def synthesize(self, text: str, voice_id: str, speed: float) -> SynthResult: ...

@dataclass
class SynthResult:
    audio: bytes            # PCM 16-bit mono 24 kHz
    sample_rate: int
    timestamps: list[WordTimestamp]   # (word, start_ms, end_ms, char_start, char_end)
```

Speeds above the backend's native range are handled by the service, not the backend: synthesize at the top of the range, then time-stretch and scale the timestamps.

**REST endpoints**

| Method | Path | Purpose |
| --- | --- | --- |
| POST | /documents | Upload a PDF; 202 {id, status=parsing} (row goes uploaded → parsing before the parse is queued); same bytes again (sha256) → 200 with the existing id and status; non-PDF → 415; over 100 MB → 413 |
| GET | /documents | Library list with progress |
| GET | /documents/{id} | Metadata (status, fail\_reason, page\_count, sha256), sections, settings, position; unknown id → 404 |
| GET | /documents/{id}/segments?from=&limit= | Ordered segments for the text view: rows with `order` ≥ from (default 0), limit default 100, clamped to 500; returns total and next\_from (null after the last page); unknown id → 404 |
| PATCH | /documents/{id} | Update voice, speed, position |
| DELETE | /documents/{id} | Remove document and cached audio |
| GET | /voices | All voices across backends |
| GET | /audio/{segment\_id}?voice=&speed= | One synthesized segment (cache hit or synthesize), with timestamps in a header or sidecar JSON |

**Audio delivery (decided 2026-10-15, replaces the earlier WebSocket plan)**

The browser fetches `GET /audio/{segment_id}?voice=&speed=` one segment at a time and keeps two decoded ahead; the server's lookahead queue keeps five synthesized ahead. On a cache miss the API blocks until the synthesis thread finishes that segment. Playback schedules each decoded buffer at the previous one's end on the `AudioContext` clock, which is gapless by construction and gives highlighting a sample-accurate clock. Seek, voice and speed changes stop the scheduled sources, refetch from the new position with the new parameters, and the server clears and refills its queue. Rationale and the rejected WebSocket + MSE alternative are in the Technical Design, D5.

## Non-functional requirements

v1 runs on one laptop (8 GB RAM, no GPU) and must feel instant; everything else is a constraint on how the code is shaped, not on what it does.

| Area | Requirement |
| --- | --- |
| Latency | First audio within 2 s of play; subsequent segments never starve playback at 2x speed on CPU (real-time factor < 0.3) |
| Throughput | Parse a 300-page born-digital PDF in under 60 s; OCR pages at 2 s/page or better |
| Offline | Whole stack runs with no network after models are downloaded once |
| Footprint | Kokoro-82M weights (PyTorch, D15) + voices < 400 MB on disk; API process < 1.5 GB RAM during playback |
| Licensing | Every model and library in v1 is Apache-2.0, MIT or BSD; nothing non-commercial (rules out XTTS-v2). Confirmed 2026-10-17: the CC-BY-4.0 dev-only data package caniuse-lite (build tooling, not shipped) is allowed |
| Privacy | PDFs and audio never leave the machine in v1; no telemetry |
| Portability | Docker Compose on macOS and Linux; Apple Silicon must work (no CUDA-only deps in v1) |
| Observability | Structured logs per request; timing for parse, synth and cache hit rate exposed at /metrics |
| Resilience | A failed segment synthesis skips with a log line and keeps playing; a failed parse marks the document failed with a reason the UI shows |
| Testability | Backends and ingestion mockable; a 20-PDF fixture set with expected segment order checked in |
| Accessibility | Keyboard-only operation; highlight contrast meets WCAG AA; respects prefers-reduced-motion |

## Milestones

```
M1 Ingest + skeleton  -->  M2 Synthesis + stream  -->  M3 Reader UI  -->  M4 Library + polish
Gate: 20 fixture PDFs      Gate: first audio in 2 s    Gate: highlight     Gate: 300-page soak
parse in correct order     at 0.5x-3x on CPU           drift < 1 word/10m  passes; Docker up
```

M1 gate: 20 fixture PDFs parse in correct prose reading order (D12): the golden comparison covers heading, body, list, caption and footnote segments. The score is word-level (D14): word-sequence edit distance over the ordered prose, ≥ 0.95 per PDF and ≥ 0.97 mean; the sentence-level score is printed as a diagnostic only.

Each milestone is one or two coding-agent sessions and ends with its gate passing in a test, not by inspection. Nothing in a later milestone starts until the gate before it is green; the gates are the acceptance tests the coding session should write first.

**What each milestone covers**

1. M1 Ingest + skeleton: ING-1 to ING-5, the `documents`/`blocks`/`segments` tables, `POST /documents` and `GET /documents/{id}/segments`, a CLI that dumps a PDF's segments to stdout for eyeballing. Start by collecting the 20 fixture PDFs: five academic two-column papers, five single-column reports, five scanned pages, five with heavy tables and equations.
2. M2 Synthesis + stream: SYN-1 to SYN-5, the Kokoro backend, the audio cache table, `GET /audio/{segment_id}` with its lookahead queue. Benchmark script that reports real-time factor and time-to-first-audio. Also (added 2026-10-16, after D14): a sentence-boundary truth independent of the extractor (ordered prose text with reviewed sentence breaks) and a boundary precision/recall metric over the word stream, gated in M2 because synthesis is where boundaries become audible; the M1 golden measures order only.
3. M3 Reader UI: PLAY-1 to PLAY-5, the React app with Web Audio scheduled playback and word highlighting from timestamps. Voice and speed pickers. Clause-level chunking of the first sentence at speeds < 1.0 (D19) is deferred to M4 (user decision 2026-10-17). The browser decode matrix for WAV and Ogg Opus (D16).
   Status 2026-10-17 (branch `m3-reader`): PLAY-1 to PLAY-5 built in `web/`; the browser gate passes on Chromium (asserted) and on WebKit and Firefox (reported, D22), 9 of 9 tests each (`_agent/results/436_e2e_chromium_gate.txt`, `437_e2e_webkit.txt`, `438_e2e_firefox.txt`); the decode matrix passes WAV and Ogg Opus on all three Playwright engines; first audio was measured in the browser against Kokoro at 0.5x, 1.0x and 2.0x (`_agent/results/445_first_audio_kokoro.txt`). Decisions taken in M3 (Technical Design D20–D25): Node installed user-local from the official tarball (D20); the Vite dev server proxies the API, no CORS, and FastAPI serves `web/dist` in M4 (D21); the gate is asserted on Chromium only (D22); voice or speed changes made while paused apply at the next Play (D23); pause is `AudioContext.suspend()` (D24); sections are derived in the client from heading segments until the server writes the sections table (ING-8, M4) (D25). Confirmed by the user 2026-10-17: D20–D25 as recorded; D19 clause chunking deferred to M4 (first-audio baselines `_agent/results/445_first_audio_kokoro.txt`, `452_first_audio_after.txt`); D16 default stays WAV until one play in the user's own Safari (M4 item). Hands-on procedure: `docs/M3_TESTING.md`; code map: `docs/CODE_MAP_M3.md`.
4. M4 Library + polish: LIB-1 to LIB-4, PLAY-6 to PLAY-8, ING-6 and ING-7, OCR fallback (ING-2), Docker Compose, the 300-page soak test. Carried from M3: clause-level chunking of the first sentence at speeds below 1.0 (D19; baselines `_agent/results/445_first_audio_kokoro.txt` and `452_first_audio_after.txt`: 0.5x cold mean 1883 ms, 1.0x 1423 ms, warm under 30 ms; script `web/scripts/measure_first_audio.mjs`); one play in the user's own Safari to settle the default audio format (D16).

After v1: SYN-7 second backend, SYN-8 content-aware delivery, PLAY-9 export, ING-9 more formats.

## Open questions and risks

The two risks that can sink v1 are reading order on real-world PDFs and highlight drift; both are mitigated by writing the gate tests before the features.

| Risk | Likelihood | Mitigation |
| --- | --- | --- |
| Reading order wrong on two-column or mixed-layout PDFs | High | Fixture set with ground truth from day one; Marker as the fallback parser for academic layouts; let the user tap a block to skip it |
| Kokoro timestamps drift from audio after time-stretching | Medium | Stay inside native speed range where possible; scale timestamps by the exact stretch ratio; drift test in CI |
| Audible seams between segments | Medium | Schedule each decoded segment at the previous one's end time on the AudioContext clock; never use `<audio src>` per segment |
| Kokoro quality judged too robotic for long listening | Medium | Backend interface makes a GPU model a drop-in; try Fish Speech on a cloud GPU before committing |
| OCR on photographed pages too slow or inaccurate | Medium | Tesseract first; PaddleOCR behind a flag; cap OCR to pages without a text layer |
| Scope creep toward summaries and chat | High | Non-goals list; v1 ships the reader only |
| M1 gate is prose-only (D12): table and equation internals are not order-checked until ING-7 | Medium | Golden test asserts the excluded character mass (table/equation chars ÷ all chars) matches the ground truth within 0.05 absolute (D14), so prose misread as table cannot hide; ING-7 (M4) adds the table/equation reading rules and their comparison |
| M1 gate is word-level (D14): segment and sentence boundaries are not order-checked by the golden test | Low | Sentence-level score still printed per PDF as a diagnostic; sentence splitting is covered by the stage-5 unit tests |

**Open questions**

- [ ] Product name decided: HearNarro; register hearnarro.com before the first push - still working
- [ ] Should speed be global or per document by default? Current plan: per document, with a global default -- this can be a global setting and the user should be able to change it
- [x] Cache format decided 2026-10-15: Opus at 48 kbps - lets go with opus. Amended 2026-10-16 (D16): WAV by default in M2, Ogg Opus at 48 kbps optional in process through `opuscodec` (`HEARNARRO_AUDIO_FORMAT=opus`); no external encoder binary. Which one becomes the default is decided in M3 with the browser matrix. Matrix run 2026-10-17: both formats decode on Chromium, WebKit and Firefox under Playwright (`_agent/results/436`–`438`, `422`, `423`); the default waits on a check in real Safari (D16)
- [ ] Is a 2 s time-to-first-audio target realistic on an M1 laptop with Kokoro-82M on PyTorch CPU (D15)? Benchmarked in M2 (the gate sentence passes at 0.5x to 3.0x, `_agent/results/311_model_tests.txt`; some 200-character sentences exceed 2 s at 0.5x, `_agent/results/314_bench.txt`, D19). Measured in the M3 browser on 2026-10-17: at 1.0x and 2.0x every cold sample was under 2 s, at 0.5x none was (3 samples each, `_agent/results/445_first_audio_kokoro.txt`); after the prefetch-order fix (67119ab) the 0.5x cold mean was 1883 ms, worst 2009 ms, on three new sentences (`_agent/results/452_first_audio_after.txt`). Decided 2026-10-17 by the user: clause chunking (D19) is deferred to M4 with these numbers as the baseline; `web/scripts/measure_first_audio.mjs` re-measures it
- [ ] Do we need Marker in v1, or does pdfplumber plus a column-detection heuristic clear the 95% gate?
- [ ] Phone browser: does iOS Safari allow background playback through Media Session? MSE is not used (D5): playback is Web Audio, which iOS pauses in a background tab. Not verified in M3 as of 2026-10-17; the muted `<audio>` workaround (Technical Design D5) is not built; Media Session is PLAY-7 (M4)
