# YomiKoe Technical Design v1

As of 2026-10-15 · Sowmya

Companion to the PRD. The PRD says what v1 does; this doc says how, and records why each alternative lost.

## Decision log

Eleven decisions shaped v1 at the start (D1–D11); three were yours to confirm (D5, D7, D10) and the rest follow from the PRD's constraints. D12–D19 were added during M1 and M2, D20–D25 during M3, D26–D30 (D27 unused) and D31–D34 (the eval layer) and D35 during M4, D36–D37 for M5 and D38–D39 for M7 Classroom view (confirmed by the user 2026-10-17; numbered M6 until 2026-10-19), D40 for M5, D41–D44 for the deferred Kindle PRD (proposed), and D45–D51 for M6 Domain reading (`docs/PRD_DOMAINS.md`, confirmed by the user 2026-10-19), D52 for the rename, and D53 for the M5 client-side pauses (SYN-8; decided by the supervisor 2026-10-17 as spec Q7, open to your confirmation). Each is argued in its section below.

| # | Decision | Recommendation | Status |
| --- | --- | --- | --- |
| D1 | PDF text extraction | Spans with bbox + font from a geometric extractor (was PyMuPDF `get_text("dict")`; replaced by D13); Marker only as an opt-in second parser | Proposed (extractor superseded by D13) |
| D2 | Reading order | Geometric: x-gap column detection per page, then top-to-bottom within column; no ML in v1 | Proposed |
| D3 | Header/footer removal | Repetition across pages (same normalized text in same band on 3+ pages) plus page-number regex | Proposed |
| D4 | Sentence splitting | pysbd on merged block text; keep char offsets back to the block | Proposed |
| D5 | Audio delivery to browser | Per-segment HTTP fetch of encoded audio (Ogg Opus by default, WAV optional, D16) + Web Audio API scheduled buffers; no WebSocket, no MSE in v1 | **Decided 2026-10-15; PRD updated; built in M3 (2026-10-17)** |
| D6 | Speed | Kokoro native 0.5–2.0x; 2.1–3.0x synthesize at 2.0x then time-stretch in-process with a numpy WSOLA (ratio ≤ 1.5; D17 replaced ffmpeg `atempo`) | **Amended 2026-10-16 (D17)** |
| D7 | Cache format | One file per (segment, voice, speed): Ogg Opus via `opuscodec` by default (needs the `opus` extra; WAV 24 kHz PCM16 mono with `YOMIKOE_AUDIO_FORMAT=wav`) (D16); no ffmpeg | **Decided 2026-10-15; amended 2026-10-16 (D16)** |
| D8 | Highlight sync | Word spans in DOM; `requestAnimationFrame` loop reads AudioContext clock; binary search over timestamps | **Decided 2026-10-17; built in M3** |
| D9 | Process model | One FastAPI process; ingestion in a `ProcessPoolExecutor` with the spawn start method (amended 2026-10-17: on Linux the default fork inherited the API's open SQLite connection into the first worker and its writes failed with disk I/O error; macOS already defaulted to spawn, so the host never showed it; `_agent/results/596`); synthesis in one dedicated thread with a single model session (PyTorch CPU, D15) | Proposed |
| D10 | Frontend state | XState-style explicit player state machine vs. plain React reducer | **Decided 2026-10-15 (plain `useReducer`); built in M3 (2026-10-17)** |
| D11 | Fixture ground truth | `*.expected.jsonl` hand-corrected once, then golden; test asserts Levenshtein on segment order ≥ 0.95 | Proposed |
| D12 | Golden comparison scope | Prose-only; figure text dropped; inline math joined; table/equation internals excluded until ING-7 | **Decided 2026-10-16** |
| D13 | Extractor: pdfplumber + pypdfium2, replacing PyMuPDF (AGPL) | pdfplumber (MIT; pdfminer.six underneath) supplies glyphs, fonts, images, vector drawings and ruled tables; stage 1 groups glyphs into lines and blocks itself in content-stream order; pypdfium2 (Apache-2.0/BSD-3) renders pages for OCR. Supersedes the PyMuPDF part of D1 | **Decided 2026-10-16** |
| D14 | Golden score granularity | Word-sequence edit distance over ordered prose; sentence-level printed as diagnostic; char-mass guard | **Decided 2026-10-16** |
| D15 | Kokoro runtime without the GPL chain | `hexgrad/Kokoro-82M` pinned at `f3ff3571791e39611d31c381e3a41a3af07b4987`, fetched with `hf_hub_download(revision=...)`; Kokoro's Apache-2.0 model code vendored and run on PyTorch CPU; base `misaki.en.G2P` without extras, an own `num2words` shim (`inflect`), and a vendored g2p_en fallback for out-of-vocabulary words. Never installed: `kokoro`, `misaki[en]`, phonemizer, espeak-ng, `num2words` | **Decided 2026-10-16** |
| D16 | Audio container | Ogg Opus at 48 kbps via `opuscodec` (Apache-2.0, in process) per segment by default (the `opus` extra must be installed; otherwise WAV fallback with a warning); WAV (stdlib) with `YOMIKOE_AUDIO_FORMAT=wav`; media type from the file extension; browser decode matrix (Safari and Ogg Opus) in M3, a WebM muxer only if needed. Replaces the ffmpeg subprocess of D7's original plan | **Decided 2026-10-16**; measured in M3 (decode matrix: WAV and Ogg Opus pass on Chromium, WebKit, Firefox under Playwright, `_agent/results/436`–`438`, `422`, `423`), **Decided 2026-10-17: Ogg Opus default** (user played document 16 with Opus clips in their own Safari, `audio/ogg`, cache purged; user report 2026-10-17) |
| D17 | Time-stretch | In-process numpy WSOLA, ratio ≤ 1.5, pitch kept, timestamps scaled by `1/ratio`; replaces ffmpeg `atempo` in D6 | **Decided 2026-10-16** |
| D18 | Sentence-boundary gate | Boundary P/R/F1 over the aligned word stream against `<stem>.sentences.txt`: F1 ≥ 0.90 per fixture, mean F1 ≥ 0.95, recall ≥ 0.97 per fixture; raised when block-boundary false positives are fixed | **Decided 2026-10-16** |
| D19 | The 0.5x time-to-first-audio gate | The M2 gate is measured on the spec sentence (passes at 0.5x); the benchmark reports the full distribution (some 200-character sentences exceed 2 s at 0.5x); M3 adds clause-level chunking of the first sentence at speeds < 1.0 and measures the wait in the player | **Decided 2026-10-16 (user)**; measured in M3 (browser first audio vs Kokoro, `_agent/results/445_first_audio_kokoro.txt`), user decision 2026-10-17: clause-level chunking of the first sentence at speeds below 1.0 deferred to M4; baselines `_agent/results/445_first_audio_kokoro.txt` (before the prefetch fix) and `452_first_audio_after.txt` (after): 0.5x cold mean 1883 ms, 1.0x 1423 ms, warm under 30 ms; script `web/scripts/measure_first_audio.mjs` |
| D20 | Node toolchain | Node LTS from the official nodejs.org tarball, SHA-256 checked against `SHASUMS256.txt`, user-local in `~/.local/node` (no Homebrew, no sudo); exact pins and a committed `package-lock.json` | **Decided 2026-10-17 (supervisor); confirmed by the user 2026-10-17** |
| D21 | Dev access to the API | The API stays CORS-free; Vite's dev server proxies `/documents`, `/audio`, `/voices` to `YOMIKOE_API` (default `127.0.0.1:8765`); FastAPI serves `web/dist` in M4 | **Decided 2026-10-17 (supervisor); confirmed by the user 2026-10-17** |
| D22 | Browser gate scope | Playback gate asserted on Chromium in M3; WebKit and Firefox run the same tests with `YOMIKOE_E2E_ALL_ENGINES=1` and are reported | **Decided 2026-10-17 (supervisor); confirmed by the user 2026-10-17**; updated in M4: every phase 2 spec also runs on WebKit and Firefox (20 passed each), still asserted on Chromium only |
| D23 | Settings change while paused | Voice/speed changes while paused or idle update context only and apply at the next Play (a fresh schedule); while playing they restart the current sentence (PLAY-4) | **Decided 2026-10-17 (supervisor); confirmed by the user 2026-10-17** |
| D24 | Pause | `AudioContext.suspend()` / `resume()`; the schedule is never rebuilt for pause/resume | **Decided 2026-10-17 (supervisor); confirmed by the user 2026-10-17** |
| D25 | Sections in M3 | Derived in the client: each `heading` segment starts a section; the API's `sections` are used when non-empty; server-side TOC (ING-8) in M4 | **Decided 2026-10-17 (supervisor); confirmed by the user 2026-10-17**; server side closed in M4 (ING-8 writes `sections` at ingestion); documents ingested earlier keep the client derivation |
| D26 | Position persistence | Position and settings saves go through one `PATCH /documents/{id}`; on `pagehide` the last value is sent with `fetch(..., {keepalive: true})`; `navigator.sendBeacon` is not used | **Decided 2026-10-17 (proposed by the supervisor, confirmed by the user)**; built in M4, not exercised in a browser |
| D28 | OCR engine (ING-2) | Tesseract as a subprocess behind `OCRBackend`, `FakeOCRBackend` in tests; a page with under 20 text glyphs and ink coverage above 0.5 % is sent; with no engine the page stays empty and `documents.ocr_skipped_pages` (migration 0004) counts it | **Decided 2026-10-17 (proposed by the supervisor, confirmed by the user)**; real engine not run (tesseract not installed) |
| D29 | Reader virtualisation | None: the M3 "load every segment" reader stays, because the 300-page soak rendered and played within the gate | **Decided 2026-10-17 (proposed by the supervisor, confirmed by the user)**; measured by the M4 browser soak |
| D30 | Packaging | One Compose service `api` built from `api/Dockerfile` that serves the API and the built `web/dist` (D21); CPU-only PyTorch; port 8765; library on a named volume (the bind-mount failure seen first on Colima was the same fork race, D9 amendment; the named volume stays the default for portability and a bind mount is a documented option) | **Decided 2026-10-17 (proposed by the supervisor, confirmed by the user)**; gate clause 3 green on Docker Desktop (`_agent/results/599`) |
| D31 | What an eval is | A scored test with the threshold removed and the per-example score kept; the existing scorers (`api/tests/golden_util.py`, `api/tests/boundary_util.py`, `api/yomikoe/quality.py`, `api/scripts/bench.py`) are reused as-is; the eval layer adds only a runner, a store of run records and a compare/report step; gate tests keep their thresholds and stay the floor | **Decided 2026-10-17** |
| D32 | Eval layout | `api/yomikoe/evals/` with `runner.py`, `store.py`, `report.py`, `scorers.py`, `suites/` (one module per EVAL-n) and `data/`; run records committed under `evals/runs/<date>_<shortsha>.json`; CLI `python -m yomikoe.evals` | **Decided 2026-10-17** |
| D33 | Compare and regressions | `compare(baseline, candidate)` flags an example whose score fell by more than 0.01 (scores in 0..1), 10 % (timing) or 1 (counts), or that newly fails; a regression is a report line, not a test failure; gate tests alone block a merge | **Decided 2026-10-17** |
| D34 | Eval scope limits | No LLM-as-judge (every scorer is deterministic or a human rubric); no user data (datasets are fixtures and committed sentence lists); Whisper (MIT) allowed as a development-only ASR dependency for EVAL-5/6, never shipped | **Decided 2026-10-17** |
| D35 | Golden floors by fixture class | The reading-order golden gate (ING-4, D14) asserts 0.95 per PDF for text-layer fixtures and 0.85 per PDF for the five `scanned_*` fixtures (OCR path); the 20-PDF mean stays 0.97 | Confirmed 2026-10-17 (user) |
| D36 | Where mathematics is spoken | Equation blocks keep their ING-3 type and their own segments; a new ingestion step after stage 5, "mathspeak", writes the spoken form into `normalized_text` for equation segments and for the inline-maths spans of prose segments, with `char_map` entries so highlighting stays honest (the whole equation maps to its spoken words); the ING-7 cue becomes the fallback output of the same step; the backend is unchanged (SYN-4) (MATH-1, MATH-2, MATH-4) | Confirmed 2026-10-17 (user) |
| D37 | Structure source for mathematics | Dependency-free first: structure from the glyphs stage 1 already keeps (math font names, superscript flag, baseline offsets, stacked bboxes for fractions, large operators from CMEX); an image-to-LaTeX model is a later option behind a flag, only if licence-clean (`_agent/research/m5-math-speech-options.md` decides) (MATH-1, MATH-6) | Confirmed 2026-10-17 (user) |
| D38 | Board as a rendered page plus overlay | Pages rendered server-side by pypdfium2 at a fixed dpi, cached under the data dir next to the audio cache; ingestion stores word boxes; the board is a second renderer of the same player state (D10), segment id plus offset selects a page and a box; pdf.js in the browser is the open alternative, decided in the M7 spec (VIEW-1, VIEW-2) | Confirmed 2026-10-17 (user) |
| D39 | Annotations are segment-anchored | One `annotations` table (Alembic migration) holding highlights, notes and bookmarks per document, anchored by segment id plus character offsets, the player's coordinates; local only, no sync; a re-ingested document (new ids, D7) loses them unless re-anchored by text match (open question) (NOTE-1 to NOTE-4) | Confirmed 2026-10-17 (user) |
| D40 | Document profile gates the speech rules | One profile pass, between stage 4 (merge) and stage 5 (segment), computes a profile (equation and inline-maths share by character mass, code share, citation style, scanned share) and a class `prose`, `mixed` or `math`, stored in `documents.profile_json`; normalization, mathspeak, citation handling and the preset default take it as a parameter; bracket groups are read or dropped by class (ING-11) | Confirmed 2026-10-17 (user direction, thresholds proposed by the supervisor) |
| D41 | Kindle devices | Fire tablets (Fire OS, Silk, Chromium-based) are a supported phone-class browser target with no device-specific code (KDL-1, KDL-2); e-ink Kindles are a non-goal: old WebKit browser without usable Web Audio, Bluetooth audio only through Audible and VoiceView, no MP3 player; jailbreak paths excluded (KOReader is AGPL-3.0) (`docs/PRD_KINDLE.md`) | Proposed 2026-10-19, not confirmed; deferred to a future implementation (`docs/PRD_KINDLE.md`); device behaviour unverified |
| D42 | Kindle ingestion boundary | DRM-protected Kindle books (`.kfx`, KFX-ZIP, encrypted MOBI/AZW/AZW3) are refused at upload with 415 `drm_protected`, no decryption attempted (KDL-4); the only Kindle ingestion path is user-owned documents downloaded from Amazon's Manage Your Content and Devices (PDF or unencrypted `.azw3`) or sideloaded originals; Kindle app caches are never read; no Amazon login, no position sync | Proposed 2026-10-19, not confirmed; deferred to a future implementation (`docs/PRD_KINDLE.md`) |
| D43 | KF8/EPUB parser | A small in-house KF8 reader, `ingestion/kf8.py` (PalmDB, MOBI/EXTH headers, PalmDOC decompression, KF8 boundary, SKEL/FRAG reassembly), stdlib only, written clean-room from the public format description, feeding a shared XHTML-to-`LogicalBlock` adapter also used for EPUB (SRC-1). Rejected: (a) a permissive library, because none exists for KF8 (KindleUnpack and `mobi` GPL-3.0, libmobi LGPL-3.0; `mobi-python` has no LICENSE file, `_agent/results/821_kindle_parser_licences.txt`); (c) a Calibre `ebook-convert` subprocess, because Calibre is GPL-3.0 and the recorded subprocess precedents are permissive binaries (Tesseract, D28; D7's ffmpeg subprocess was removed by D16, `_agent/results/822_d7_subprocess_precedent.txt`) (KDL-3, KDL-5) | Proposed 2026-10-19, not confirmed; deferred to a future implementation (`docs/PRD_KINDLE.md`) |
| D44 | Document format and origin | Migration 0006 adds `documents.format` (TEXT NOT NULL DEFAULT 'pdf'; set from the content sniff; also serves M8's file type in LIB-1) and `documents.origin` (TEXT NULL; `kindle`, later other SRC origins); no existing column fits: `documents` has `filename` only and `LogicalBlock.source` is per-block provenance (`_agent/results/823_ingestion_interface.txt`) (KDL-6) | Proposed 2026-10-19, not confirmed; deferred to a future implementation (`docs/PRD_KINDLE.md`) |
| D45 | Profile fields | ING-11 profile gains a multi-valued `fields` set beside the `prose`/`mixed`/`math` class, detected from token densities, user-overridable, re-normalizing without re-ingesting (DOM-22) | Confirmed 2026-10-19 (user) |
| D46 | One wording per symbol per role | `math_convention.json` entries may carry role-keyed wordings selected by operand class or span type; banned wordings stay banned in every role | Confirmed 2026-10-19 (user) |
| D47 | Units as expressions | Units are parsed as expressions (prefix, unit, power, product, quotient), not token by token; "per" is the units reading of `/`, "over" the maths reading (DOM-1) | Confirmed 2026-10-19 (user) |
| D48 | Shared data tables | Shared data tables in one place under `api/yomikoe/ingestion/` (element symbols and names, polyatomic ions, units and prefixes, currencies, per-field abbreviations, reference works), each a data file with its own unit tests; no table is duplicated per field | Confirmed 2026-10-19 (user) |
| D49 | Normalization order | Inside normalization: (1) sentence-split protections for abbreviation dots; (2) whole-token tables (references, citations, tickers, gene symbols, `y/y`, `n/m`, HGVS); (3) number-anchored grammar (currency, units, scientific notation, uncertainty, ranges, ratios, data units, coordinates); (4) field-gated rules (formulas, regnal numerals, clinical shorthand, statistics position); (5) today's `_speak_symbols` and mathspeak with role-keyed entries; (6) SYN-4 and the lexicon in the backend | Confirmed 2026-10-19 (user) |
| D50 | EVAL-11 | EVAL-11 with per-domain floors, tier 0, same scorer as EVAL-10 (DOM-27) | Confirmed 2026-10-19 (user) |
| D51 | Per-document reading settings | Per-document reading settings (`jurisdiction`, `read_quantity_names`, `read_tables`, `quote_marks`) stored with the document like the ING-11 override (DOM-23) | Confirmed 2026-10-19 (user) |

## Ingestion pipeline

```
1 Extract          2 Classify            3 Order (the risky stage)   4 Merge              5 Segment
PDF glyphs     ->  heading, body,    ->  detect columns          ->  join lines       ->  pysbd sentences
bbox, font, size   caption, footnote,    drop header/footer          de-hyphenate         char offsets kept
OCR if no text     header/footer, table  linearize                   cross-page flow      normalize for TTS
in: one PDF page at a time                                       out: segments rows, in reading order
```

Ingestion is a pure function from a PDF to a list of segments, run once per upload in a worker process; every stage is a separate module with its own unit tests so a bad reading order can be blamed on one stage.

**Stage 1, extract (D1, D13).** pdfplumber (pdfminer.six) yields every glyph in content-stream order with its bbox, font name, size and `upright` flag; coordinates are converted to a top-left origin. Stage 1 groups glyphs itself rather than using pdfminer's layout analysis (which splits justified lines at wide word gaps and inline maths into many boxes): a glyph continues the current line when it overlaps it vertically by ≥ 30% and starts between 0.5 font sizes left and 10 font sizes right of the previous glyph; a gap wider than 0.15 font sizes becomes a space. A line joins the current block when it overlaps the block, or starts at most 0.5 font sizes below it, overlaps it horizontally and its font size is within 1.25×. Lines then become spans by (font, size, superscript): bold from font names containing Bold/Black/Heavy/Semibold/Demi/Medi/CMBX or ending ",B"/"-B", italic from Italic/Ital/Oblique/CMTI; superscript = a glyph ≤ 0.75× the line's dominant size whose bottom sits > 0.2 dominant sizes above the line's baseline. `Line.dir` is (1, 0) when every glyph is upright, else (0, 1). Unmapped TeX glyphs (`(cid:N)`) become the ASCII code point. Images come from `page.images`; figure regions (D12) from `page.rects`/`curves`/`lines`; tables from `page.find_tables()` keeping only tables with ≥ 2 rows and ≥ 2 columns. Keep spans, not just text: font size drives heading detection and bbox drives everything else. Pages whose text layer yields fewer than 20 characters are rendered at 300 dpi with pypdfium2 and sent to Tesseract (`image_to_data` for word boxes), producing the same span structure. Stage 2–4 thresholds were tuned against PyMuPDF output; on this extractor the golden mean fell from 0.9285 to 0.6963 (_agent/results/104_golden_pdfplumber.txt); tuning round 3 (below) brought it to 0.9203 (_agent/results/144_golden_final.txt). Marker is wired behind a `YOMIKOE_PARSER=marker` flag for the academic fixtures; it is not the default because it pulls in PyTorch and GPL code.

**Stage 1 rules added in tuning round 3 (tuned 2026-10-16 on pdfplumber; `extract.py`).** They reproduce the MuPDF behaviour the D11/D12 ground truth was drawn from.
- *Glyph boxes:* a font whose usual descent (baseline minus box bottom) exceeds 0.8 sizes (pdfminer hangs CMSY glyphs ~0.96 em low) is lifted to a 0.25 descent, per font so that rise is kept.
- *Tracked text:* a line of ≥ 6 tokens (runs between word spaces), ≥ 70% of them single letters but not all, with no maths-font glyph, is letter-spaced: every glyph gap exceeded the word-space threshold. Its spaces between tracked fragments (one glyph, or a kerned capital pair such as "OT") are kept only where the gap is ≥ 2 × the median gap between fragments, so "G E T T I N G R I C H" reads "GETTING RICH"; spaces next to ordinary words are untouched. A line of single letters only is left spaced for the stage-2 banner rule (found on a user book 2026-10-16).
- *Lines:* an overstrike (an accent then its letter, "/" over "∈") that steps back onto the previous glyph continues the line, and accent glyphs (spacing accents, CMEX wide hats mapped to "b".."g") skip the vertical-overlap test.
- *Spaces:* the gap is measured in the next glyph's size, as MuPDF does. A baseline jump of more than 0.8 of the next glyph's size (stacked scripts, limits, radicals) also reads as a space. No space is inserted after a CMSY/CMR relation, arrow, minus, ∗ or ∆ (`∈≤∼−→∥⊤⊥⊗∞`…), nor after an accent; "|", "×", "·", "′" and "†" keep theirs.
- *Ligature glyphs (found on a user PDF 2026-10-16):* some subset TrueType fonts map their ligature glyphs to ASCII punctuation in ToUnicode ("Ful!lled", "e#ort", "$avor"), and which character stands for which ligature changes from font to font (PDFium reads the same punctuation, _agent/results/215_ligature_diagnosis.md). For each simple TrueType font with an embedded program (`FontFile2`) and a ToUnicode map, the character code is looked up through the program's own `cmap` (subtable (3,0), (1,0) or (3,1); formats 0, 4, 6) and named from its format-2 `post` table; when the glyph name is a ligature (`f_i`, `f_f_i`, any AGL underscore name of single letters such as `f_f_b`, `fi`/`ffi`/`ff`/`fl`/`ffl`/`ft`, `uniFB00`–`uniFB04`) and ToUnicode gives one ASCII non-alphanumeric character, the glyph's text becomes the ligature's letters; the bbox is kept. A (font name, character) pair two fonts on a page disagree on is left alone. Glyphs named from the Macintosh standard set (post index < 258) are not resolved.
- *Low CID codes:* `(cid:N)` with N < 32 becomes the control character, as PyMuPDF emitted it, so CMEX delimiters stay equation segments.
- *Blocks:* a line starting more than 0.5 pt right of the previous line's start opens a block when the PDF is tagged (glyphs carry MCIDs: Word/Acrobat), when the move is at most 2 pt (the previous line hung into the margin), when both lines are centred within 3 pt and the new one starts at least 5 pt further right (titles, author lists), or when the previous line opens a numbered reference ("[12] …"). Larger hanging indents in untagged PDFs (list items, wrapped headings) keep the block. The ≤ 2 pt rule also fires mid-paragraph in books set with optical margin alignment (line starts jitter 0.5–1 pt); it is kept because the golden ground truth holds those splits, and stage 4 rejoins them where they are systematic. A baseline more than 1.6 sizes below the previous line's opens a block even when tall glyphs make the boxes touch.
- *Display maths:* a line holding a math-font glyph (CMMI/CMSY/CMEX/CMBSY/MSBM/MSAM/RSFS/EUFM/"Math") whose text-font letters at ≥ 0.8 of its dominant size are under 30% of its glyphs is a math line. On a new text row, a change between math and prose lines opens a block.
- *Booktabs tables:* `find_tables` needs vertical rules. A stack of ≥ 3 thin horizontal rules (≤ 1.5 pt high, ≥ 50 pt wide) sharing their x-extent within 3 pt, each within half the page height of the next, bounds a table region. The region counts only if ≥ 2 text lines inside have a glyph gap wider than 1 font size; this rejects title pages framed by rules, even with a letter-spaced banner. These regions join `table_bboxes`.
- *Figure regions:* curves are padded by 6 pt before the touching-union, so the separate boxes and arrows of a vector diagram form one figure. Plain rects are not padded, because padding them merges the shaded rows of report text boxes into figures. Thin wide rules never seed a figure.

**Stage 2, classify.** Rules, in order, first match wins:

| Type | Rule |
| --- | --- |
| noise (off-page blocks unless heading-sized) | Off-page blocks are noise unless their largest span is at least body size. Off-page means less than 50% of the block's bbox area lies inside the page box [0, width] × [0, height] (top-left coordinates as pdfplumber reports the page). First rule, and re-applied after the document passes so no later pass retypes it; blocks trimmed at the edge with ≥ 50% inside fall through. An off-page block whose max span size ≥ 1.0 × the body median (`OFF_PAGE_KEEP_SIZE_RATIO`) goes through the normal cascade and is read (user decisions 2026-10-16; a book's back cover at x < 0: the tagline, ratio 1.109, is kept as body; the blurb and bio, ratios 0.589–0.762, stay noise) |
| noise (margin stamp) | Any line with text has `Line.dir` other than (1, 0) and the block lies in the outer 10% of the page width (arXiv and NIST DOI stamps); rotated figure labels inside the page fall through |
| header / footer | Block lies in the top or bottom 8% band (by bbox, or by vertical midpoint) and its normalized text recurs in that band on 3+ pages, or matches `^\d+$`, a lower-case roman numeral, `^Page (\d+\|roman)`, `^\d+ of \d+$`, or (no repetition needed) it has ≤ 3 non-empty lines and either ≥ 60% of its letters upper-case or max span size ≤ 0.95 × body median |
| noise (boilerplate) | Every non-empty line is email/URL-only, `Preprint.`, `Under review.`, `This publication is available free of charge from…`, or a rule of `_`/`-`/`=`; or the block is a letter-spaced banner (≥ 6 single-letter tokens); or, on the first 2 pages and in the bottom 30%, it mentions `Department of Commerce`, `Secretary` or `Director` (cover signature block); or every line is leader dots (`^[\s.·…]+$` with ≥ 3 dots, any page); or the text is only punctuation (Unicode `P*`: quotes, dashes, `*`), except a bare `.` `,` `;` `:` `!` `?` which is left to the equation rule (found on a user PDF 2026-10-16) |
| heading | Font size ≥ 1.15 × body median, or bold and ≤ 12 words and no terminal period |
| caption | Starts with `Figure`, `Fig.`, `Table` or `Listing` + number, and sits within 40 pt of an image or drawing bbox |
| footnote | Font size ≤ 0.85 × body median and in bottom 25% of page and more than 3 non-space chars (1–3 char fragments are equation sub/superscripts), or line starts with superscript digit and the block starts in the lower half of the page (above it: an affiliation line; tuned 2026-10-16 on pdfplumber) |
| table | Block overlaps a table region (`page.find_tables()` or a booktabs rule stack). A block centred inside one is typed table before the heading/caption/footnote rules, so bold header rows stay table (tuned 2026-10-16 on pdfplumber). Exception, page 0 only: a region whose blocks hold no digit, ≤ 4 lines in all, and are all at heading size (≥ 1.15 × body median) is a ruled title frame and is ignored, so the cover title and authors fall through to heading (found on a user PDF 2026-10-16) |
| equation | Majority of chars are math symbols or in a math font (`Math`, `CMSY`, `CMMI`, `CMEX`, `CMBSY`, `MSBM`, `MSAM`, `RSFS`, `EUFM`). Also an equation: a block holding a math-font glyph whose text-font letters at ≥ 0.8 × its largest size are under 50% of its characters, or a bare equation number `(n)` (tuned 2026-10-16 on pdfplumber) |
| list item | First line is an item line (`ITEM_RE` in `models.py`): after optional whitespace it starts with a bullet glyph (`• · ▪ ▫ ■ □ ● ○ ◦ ‣ ► ▶ ➢ ➤ → ⇒ ✓ ✔ ✗ ✘ ★ ☆`), with `-` `–` `*` followed by a space (so `-based`, a hyphenated word wrapped to a line start, is not an item; `—` is not a bullet, `— Wired` is an attribution), or with a marker `1.` `1)` `(1)` `a.` `a)` `(a)` `iv.` followed by a space. Later lines of the block may be item lines or continuations (a wrapped item) |
| body | Everything else |
| body (cover pull quote) | Pass after the cascade, first 2 pages: a run of consecutive blocks typed heading by the size rule whose joined text starts with an opening quote (`“ " ‘ « „`) or holds ≥ 2 sentence ends (`[a-z]{2,}[.!?]` + optional closing quote, then space or end) is retyped body, one block each, not merged. A one-line title with no terminator stays heading (found on a user PDF 2026-10-16) |
| noise (vertical-title letter) | First 2 pages: a single rotated letter (plus optional `.,;:!?`) in a text font with no other block on its text row within 3 × its height (found on a user book 2026-10-16) |
| heading (vertical title) | Pass after the cascade, every page: single-letter blocks (types heading, body, noise, footnote, caption, list) whose x0 lie within 10 pt, sorted by top, split where a gap exceeds 2 × their median height; each run of ≥ 5 folds into one heading (letters joined, a word break where the gap exceeds 1.5 × the run's median gap), marked `lead` so stage 3 reads it first on the page; the other letters become noise (found on a user book 2026-10-16) |
| noise (drop cap) | Pass after the vertical-title fold, every page: a heading or body block whose text is one capital letter `[A-Z]` with largest span ≥ 1.5 × body median is a drop cap when a body block on the page starts with a lowercase letter and its first line's top lies within the cap's vertical extent and its first line starts no more than 1 pt left of the cap; the letter is prepended (no space) to the topmost such block's first span and the cap becomes noise (found on a user book 2026-10-16) |
| toc | Pass after the cascade, whole document in page/block order (header, footer, figure blocks skipped): a block of any type (a contents line may be typed body) whose normalized text is `contents` or `table of contents` opens a region. A block is TOC-like if it is one leader-dot line or one page number alone (`^\d{1,4}$` or a lower-case roman numeral `^[ivxlc]+$`), or ≥ 50% of its lines are leader dots, end in a page number (`\d{1,4}\s*$`) or hold ≥ 2 inner numbers (`\s\d{1,4}\s`, titles and page numbers run together). TOC-like blocks join the region, across pages; blocks of ≤ 2 lines before the first TOC-like one join it too, and after it a block of ≤ 2 lines that is not a sentence joins when a TOC-like block follows within the next 3 blocks with no sentence or longer block before it (an entry title above its page-number block). A sentence is ≥ 4 words ending in `.`, `!` or `?` (before closing quotes or brackets). The region ends at the first other block once a TOC-like block was seen (so at a sentence such as a dedication), at a heading of body-median size or larger, or after 6 pages. If it saw a TOC-like block, every block in it (heading included) is typed `toc`, which is never read (not in `READ_TYPES`); otherwise nothing changes (found on a user PDF 2026-10-16) |

After the first match, any block except a caption whose bbox lies ≥ 80% (by area) inside a figure region is retyped `figure` and never read (D12). Figure regions are computed per page in stage 1 (`Page.figure_bboxes`): every image bbox, plus the bbox of each transitive union of touching or overlapping `page.get_drawings()` rects whose area is 2%–80% of the page (smaller unions are rules and boxes, larger ones page backgrounds).

Body median font size is computed per document, not per page, so a page of all-headings does not fool it.

**Stage 3, reading order (D2, D3).** Per page: blocks marked `lead` by stage 2 (folded vertical titles) come first, by top y, and take no part in column detection. Then take blocks typed body, heading, list, caption, equation (drop header/footer; defer footnotes to the end of the page). Blocks with no text, `noise` and `figure` blocks are dropped. Columns come from a gutter search over the blocks no wider than 60% of the page: every x in the middle half of the page is a candidate whose cost is the text (chars) of blocks straddling it, except blocks that reach more than 5% of the page width past it on both sides (those are spanning figure/table text and cost nothing). Two columns iff a run of equal-cost candidates at least 1.5% of the page width wide is straddled by ≤ 5% of the narrow text, has ≥ 10% of it on each side, and narrow blocks hold ≥ 50% of the page's text (a single-column page with inline-math fragments stays one column); split_x is the centre of the cheapest such run. Assign each block to the column its midpoint falls in; blocks wider than 60% of page width are full-width and act as column breaks (a figure spanning both columns ends the current column run). Within a column, sort by top y. Inline maths: PyMuPDF splits a line with inline maths into several blocks, so after linearizing, each prose block (body or list, ≥ 30 non-space chars; display-equation pieces are never hosts) pulls in the body/equation/list fragments that continue its last text line: first text line overlapping that line vertically by ≥ 80% of the shorter line, centred no more than 0.4 font sizes below it (sum limits and fraction denominators stay put), starting between 0.75 font sizes left and 1 font size right of where the line ends; the leftmost such fragment among the next 10 blocks (or a one-line fragment sorted just before the host) follows the host, and the search repeats from the fragment. Every fragment in the chain is marked inline and stage 4 joins it into the host's text, whether or not the extraction order had split the chain (D12); display equations (own block, own line) never overlap a prose line and stay separate. Emit column 1, column 2, then footnotes. This clears two-column academic papers and single-column reports; three-column magazines and sidebars are out of scope for v1 and will fail the gate visibly rather than silently. Thresholds in stages 2–4 tuned 2026-10-15 against the fixture set (inline-maths rule added in tuning round 2; a row-major reading of full-width table zones was tried and dropped because it lowered the mean).

**Stage 4, merge.** Join lines inside a block with a space; if a line ends in `-` and the next line starts lowercase, drop the hyphen and join without a space. Body block B joins the previous body block A across a flow break (B on the next page, or B starting above A on the same page, i.e. a new column) when B starts lowercase, or B is on the next page and A lacks terminal punctuation. Only floats may lie between them (caption, table, footnote, and body or heading text in a font smaller than 0.85 × A's, i.e. figure labels); a heading, list or equation ends the candidate. When floats lie between, only B's first sentence (pysbd) moves up into A and the rest of B stays after the floats. Without a flow break, body block B joins the body block A directly before it on the same page when B starts within 1 font size below A, A ends with a line-end hyphen (de-hyphenated) or without terminal punctuation (`.!?:;"”’)`), and B starts lowercase or with an opening bracket/quote then lowercase. This same-page join is on only when the document has ≥ 10 such pairs making up ≥ 15% of its body blocks (stage 1 split paragraphs systematically: a user book had 350 pairs, 0.23; the golden fixtures at most 8, 0.13, and joining them changes the golden ground truth) (found on a user book 2026-10-16). A block marked inline by stage 3 is appended to the previous logical block (space-joined, keeping that block's type). Email-only and boilerplate lines are dropped from kept blocks, and on page 0 before the "Abstract" block email tokens are stripped from author/affiliation lines. A list block is never joined with a neighbour and is split into items: each item line plus the continuation lines after it (lines that do not start an item) becomes one logical block of type list, its lines joined as above (hyphen rule included); a line holding several glyph items (`→ a → b`) is split before each glyph that has whitespace before it and a word, bracket or quote after it (`≥· · · ≥`, a dot-leader ellipsis, is not split); a glyph alone on its line takes the next line as its text.

**Stage 5, segment (D4).** pysbd (`clean=False` so offsets stay valid) splits each logical block into sentences; each sentence keeps `(block_id, char_start, char_end)` into the block's merged text. Three passes then correct pysbd's spans, all on offsets, so `block.text[char_start:char_end] == text` holds by construction (ING-5): (1) closers: a span that starts with closing quotes or brackets (`”`, `’`, `)`, `]`) gives them to the previous span, so a quote after terminal punctuation stays with its sentence (`“stop.” Then`); (2) merges: a split is undone after an abbreviation from `api/yomikoe/ingestion/abbreviations.py` (data, grouped as titles, citations such as `Natl. Inst. Stand. Technol. Spec. Publ.` and `et seq.`, Latin such as `e.g.` `i.e.` `cf.` `vs.`, document references such as `Fig.` `Eq.` `Thm.`; `No.` `Vol.` `pp.` only before a number; `etc.` `Inc.` `al.` only when the next text does not start with a capital), after a bare section number (`2.1.` + heading), after an initial in a name list (`(P. Smith`, `W. Q. Leong`, `[9] R. Ng`), after an unterminated span followed by a lowercase or digit start or by maths notation (`PA (i), CH (i)`, `(System 1)`), and before a span starting with `,` `;` or a hyphen; numbered list items (`habits` / `2. Stabilized`) and parenthesized list items (`and (ii) when`) stay split; a pysbd split inside a token with word characters on both sides (`PA(i)`) is left alone because the M1 word-level golden (D14) counts the halves as two words; (3) letter splits: a one-letter variable after a lowercase word ends a sentence before a capital (`kernel P. Its`), which pysbd never splits, except after `and` or inside a `[n]` reference entry. `split_sentences` takes an `AbbreviationSet` so a document can extend the defaults later. Splits at block boundaries come from stages 1–4 and are not corrected here. Normalization writes `normalized_text` beside `text` and never changes offsets: `[12]` → dropped, `et al.` → "et al", `3.2%` → "3.2 percent", URLs, bare domains and e-mail addresses → spoken as read ("shopping.com" → "shopping dot com", "https://angel.co/syndicates" → "angel dot co slash syndicates", "name@host.com" → "name at host dot com"; scheme and `www.` dropped; a path longer than 3 segments or 30 chars dropped), each spoken "dot"/"slash"/"at" mapped onto its source character. The splitter does not end a sentence at `www.` before a host (a PDF line break inside an address). All-caps tokens are left as written: whether "TED" is spoken or "PDF" spelled is decided by the synthesis backend (`api/yomikoe/synthesis/acronyms.py`: overrides, collocations such as "TED talk", the document's own definitions, the pronunciation lexicon, then a pronounceability heuristic). Stage 5 also collects the document's acronym definitions, `<Capitalized words> (ACR)` and `ACR (<words>)` whose initials spell ACR (`api/yomikoe/ingestion/acronyms.py`), into `documents.acronyms_json`; the synthesis service passes them to the backend as `SynthContext`, so a defined short initialism ("Transferable Erosion Deposit (TED)") is spelled. A list item is its own logical block, so it is one segment unless it holds a sentence end mid-item (`→ Total honesty at all times. It’s almost …` gives two). The glyph and the space after it stay in `text`; normalization emits nothing for a leading glyph bullet (or `-` `–` `*` before a space) and the whitespace around it, so `normalized_text` starts at the first word and `char_map` maps it back exactly. Numbered markers (`1.`, `a)`) are kept and spoken.

**What this does not do in v1.** No ML layout model, no RTL or vertical text, no multi-column detection beyond two, no reading of table cell structure (ING-7 reads rows as prose). Each is a known gap the fixture set will expose, and each slots in as a replacement for one stage without touching the others.

## Segment model

A segment is one sentence with three coordinate systems pinned together by character offsets; everything the reader does (highlight, seek, resume, skip) is an operation on segment ids and offsets, never on raw text.

```python
@dataclass
class Segment:
    id: int
    document_id: int
    block_id: int
    order: int                 # 0..N-1, reading order across the whole document
    section_id: int | None
    text: str                  # exactly as extracted, shown in the reader
    normalized_text: str       # what the TTS reads; may differ in length from text
    char_start: int            # offsets into the block's merged text
    char_end: int
    char_map: list[int]        # for each char in normalized_text, the index in text it came from
```

`char_map` is the piece that makes highlighting honest. The TTS returns word timestamps against `normalized_text`; the reader shows `text`. Without the map, "3.2 percent" (11 chars) highlighting "3.2%" (4 chars) would drift by 7 characters and the error compounds across a sentence. The normalizer builds the map as it rewrites; a dropped citation maps to an empty range, an expanded number maps every output char to the span of the input token.

Word timestamps from the backend carry `(char_start, char_end)` into `normalized_text`; the API translates them through `char_map` before sending to the browser, so the browser only ever sees offsets into `text`. The browser pre-splits `text` into word `<span>`s with `data-start`/`data-end` and finds the active span by binary search on `start`.

Why sentences and not paragraphs: Kokoro's quality drops and latency grows past \~300 characters, a sentence is the natural seek and resume unit, and a mid-sentence voice change (PLAY-4) is simplest when the unit of synthesis is the unit of playback.

## Synthesis service

The service owns one `TTSBackend`, one cache and one lookahead queue per active document; the backend is the only thing that knows Kokoro exists.

**Kokoro specifics.** `hexgrad/Kokoro-82M` (Apache-2.0) on PyTorch CPU (D15), pinned at revision `f3ff3571791e39611d31c381e3a41a3af07b4987` and fetched with `hf_hub_download(revision=...)`: 82M parameters, 24 kHz output, voices named by language and gender (`af_heart`, `am_michael`, `bf_emma`, `bm_george`…), and a `speed` float the model applies in its duration predictor. The PyPI `kokoro` package is not used: it declares `misaki[en]`, whose extras are GPL/LGPL (phonemizer, espeak-ng, num2words), so Kokoro's Apache-2.0 model code is vendored (`yomikoe/synthesis/kokoro_model/`) and `KokoroBackend` drives `KModel` with base `misaki.en.G2P` itself, with an own `num2words` shim and a g2p_en-based fallback for out-of-vocabulary words. Word timings come from the model's predicted durations per phoneme (25 ms frames); the backend joins tokens into whitespace words, keeping the first token's start and the last token's end. All-caps headings and emphasized runs ("ERIC'S NOTE", "PART I: WEALTH") are case-folded to ordinary words before misaki's G2P (which otherwise spells unknown all-caps words letter by letter), so the acronym decision (spoken or spelled) applies only to caps tokens outside such a context and to `SPELLED`, `SPOKEN` and document-defined acronyms inside one. Measured on an Apple M5 Pro CPU (`bench/2026-10-16.json`): RTF ≈ 0.08 at 1.0x, warm first audio 0.86 s mean for 80–200-character sentences, cold start (imports + load) ≈ 2.3 s, so the model loads in the lifespan.

**Speed (D6).** The API accepts 0.5x to 3.0x in 0.05 steps (SYN-3; 1.25x, 1.75x, 2.25x are valid, 1.23x is 422), and cache keys and file names carry two decimals (`af_heart_1.25.wav`, `af_heart_2.00.wav`); rows written before the 0.05-step change keep their stored one-decimal path (`af_heart_2.0.wav`) and still hit, because the cache reads the file from the row's `path`. Kokoro is clean between 0.5x and 2.0x; above that the duration predictor produces clipped consonants. So: for requested speed ≤ 2.0, pass it to the model and cache at that exact speed. For 2.05–3.0, synthesize at 2.0 (one cache entry), then time-stretch the PCM in-process with WSOLA (D17: numpy, no new dependency and no subprocess; Hann frames of 1024 samples at 24 kHz, synthesis hop 512, analysis hop `512 × ratio`, each frame placed within ±256 samples where it best continues the previous one, so pitch is kept; ratio = speed / 2.0 in (1.0, 1.5], exactly 1.125 for 2.25x; output length within 2 % of `len/ratio`) and scale every timestamp by `1/ratio` (floored, clamped to the stretched duration). Stretched output is cached too, keyed by the requested speed, alongside the 2.0x file. This keeps the cache from exploding (users scrub through speeds) while keeping word sync exact. Native speed keeps the leading BOS token at its speed-1.0 duration (never shorter): Kokoro divides every predicted duration by speed, BOS included, and the model renders its first ~250-330 ms as near-silence, so at 2.0 the shortened BOS (175 ms instead of 325 ms) put the first word inside that dead start and it was lost (onset 73-112 ms after the first word's timestamp, first word 19-46 dB quieter than at 1.0; upstream `KModel` identical). The floor lives in `KokoroBackend._infer`; it adds 100-175 ms of leading silence at 1.5-2.0, leaves speeds ≤ 1.0 bit-identical, and keeps the native range (0.5, 2.0): lowering the native maximum does not help (1.5-1.8 clip too) and a leading pause phoneme does not either (`_agent/results/343_onset_table.md`, `348_onset_after.md`).

**Silence trim (SYN-1).** Kokoro wraps each sentence in ~315 ms of leading and ~470 ms of trailing near-silence at 1.0x, a ~0.8 s pause between sentences played back to back (`_agent/results/369_silence_table.md`), so the service passes every clip through `trim.py` → `trim_silence` right after the backend returns and before any stretch: silence at or below −40 dBFS is cut to `YOMIKOE_TRIM_LEAD_MS` (default 60) before the first sound and `YOMIKOE_TRIM_TAIL_MS` (default 150) after the last, never closer than 20 ms to the first word's `start_ms`, every timestamp shifted by the head cut and clamped to the new duration (measured gap between two trimmed sentences 210 ms vs 854–872 ms untrimmed, `377_wavs.txt`).

**Cache.** Key is `(segment_id, voice_id, speed, backend_name)`; value is a file path plus the timestamp JSON. The key uses `segment_id` not a text hash because re-ingesting a document creates new segment ids and should not reuse stale audio. The cache is write-through: synthesize, encode, write file, insert row, then return. Eviction is manual (LIB-4 delete) in v1; a size cap with LRU is a one-line addition later.

**Lookahead queue (SYN-5).** When playback starts at segment `k` with `(voice, speed)`, the service enqueues `k..k+N` where N = 5. As each finishes, the next is enqueued so the window slides. The queue is a plain `asyncio.Queue` of jobs consumed by the single synthesis thread; a seek or voice/speed change clears the queue and refills from the new position. A job whose cache entry already exists is skipped. The first segment of a play request jumps the queue so time-to-first-audio is one synthesis, not six.

**Worker model (D9).** A PyTorch CPU model already spreads one forward pass over every core, so parallel synthesis on a laptop gains nothing. One dedicated thread, one session, jobs serialized: predictable latency and no lock bugs. The FastAPI event loop hands jobs over with `loop.run_in_executor(synth_executor, job)` where the executor has `max_workers=1`. A second backend on a GPU gets its own executor.

**Failure.** A backend exception on one segment logs with the segment id, marks the cache row `failed`, and the queue moves on; the player skips a failed segment with a 200 ms silence so playback never stalls on a bad sentence.

## Audio delivery and playback (D5)

Recommendation: drop the WebSocket and Media Source Extensions from the PRD and deliver audio as one HTTP GET per segment, played through the Web Audio API with buffers scheduled back to back. It is simpler to build, gapless by construction, and gives the highlight loop a sample-accurate clock.

```
Browser (Web Audio)            API                              Synthesis thread
  |-- GET /audio/k?voice&speed -->|                                    |
  |                               |-- cache miss: synthesize k ------->|  (jumps queue)
  |                               |<-- PCM + timestamps; encode (D16) -|
  |<-- 200 audio/wav|ogg + X-Timestamps --|                            |
  decodeAudioData, schedule at t0, start highlight loop               |
--- both sides run ahead ------------------------------------------------
  |                               |-- enqueue k+1 .. k+5 ------------->|
  |-- GET k+1, k+2 (prefetch) --->|                                    |
  |<-- cache hit, or wait on in-flight job --|                         |
  schedule k+1 at t0 + dur(k): gapless, sample-accurate               |
--- seek or voice/speed change -------------------------------------------
  stop sources; GET /audio/j (new voice/speed) -->|-- clear queue, refill from j -->|
```

**Why not MSE over a WebSocket (the PRD's original plan).** MSE is designed for one continuous media stream; feeding it a sequence of independently encoded Opus segments means managing `SourceBuffer` append windows, timestamp offsets per segment and the "quota exceeded" eviction dance, and iOS Safari only supports MSE via `ManagedMediaSource` on 17.1+. A WebSocket adds a stateful connection to reconnect, resume and multiplex per document. None of that buys anything at sentence granularity: segments are 1–10 s of audio, and the browser can simply ask for the next one.

**Why Web Audio.** `AudioContext.decodeAudioData` turns a WAV or Ogg Opus response (D16) into an `AudioBuffer`; an `AudioBufferSourceNode.start(when)` scheduled at `t0 + sum(previous durations)` plays each segment exactly when the previous one ends, with no gap and no click, because the audio thread does the splicing. `audioContext.currentTime` is a monotonic hardware clock the highlight loop can read every frame. Speed is already baked into the audio, so `playbackRate` stays 1.0 and pitch is never touched in the browser.

**Protocol.** `GET /audio/{segment_id}?voice=af_heart&speed=1.5` returns the encoded segment (`audio/ogg` by default, `audio/wav` with `YOMIKOE_AUDIO_FORMAT=wav`, D16) with an `X-Timestamps` header carrying the word timestamp JSON (translated to `text` offsets) and `X-Duration-Ms`. The API blocks on a cache miss until the synthesis thread finishes that segment; the client sets a 15 s timeout. A `HEAD` on the same URL answers 200 or 404 so the client can probe cache state without downloading. The client keeps two segments decoded ahead of the one playing; the server's lookahead queue keeps five synthesized ahead, so the client's prefetch almost always hits the cache.

**Seek and settings change.** Stop every scheduled source node, clear the client buffer, fetch the target segment with the new `(voice, speed)`, and start a fresh schedule at `currentTime + 0.05`. The server sees the new request, clears its queue for this document and refills from the new position. A speed change mid-sentence restarts that sentence from its beginning, which PLAY-4 allows and which users read as "it repeated the sentence" rather than a glitch.

**What this costs.** One HTTP request per sentence: \~1,000 requests for a 40-page paper over a listening session, all small and all cached after the first pass. HTTP/1.1 keep-alive handles that comfortably on localhost; if it ever matters, HTTP/2 via uvicorn behind Caddy fixes it without touching the client. Background playback on iOS Safari is a real gap: Web Audio pauses when the tab is backgrounded. Mitigation for M3 is to also route the output through a `MediaStreamAudioDestinationNode` into a muted-then-unmuted `<audio>` element, which is the known workaround; it is an experiment, not a promise, and is already an open question in the PRD.

**What changes in the PRD if you accept this.** SYN-5's queue stays server-side as described. PLAY-5 (gapless) is satisfied by scheduling rather than by stream stitching. The WebSocket `/play/{document_id}` endpoint is removed; the stack table's "Opus/WebM to the browser" and "MSE" entries become "Opus/WebM per segment" and "Web Audio API". Confirmed; the PRD carries those edits.

## Highlight sync (D8)

The highlight never guesses: every frame it asks the audio clock where playback is, converts that to a segment and a word, and sets one CSS class. There is no timer that can drift.

**Clock.** For each scheduled segment the client records `startAt` (the `AudioContext` time it was scheduled) and `durationSec`. On each `requestAnimationFrame`, `elapsed = audioContext.currentTime - startAt` for the segment whose window contains `currentTime`. That is the position in milliseconds into that segment's audio, with no accumulated error because `currentTime` is the hardware clock the audio thread itself uses.

**Word lookup.** The segment's timestamps are sorted by `start_ms`; a binary search on `elapsed_ms` finds the active word in O(log n). The reader pre-renders each segment as `<span class="seg" data-id>` containing `<span class="w" data-i>` per word, so the active word is `seg[data-id] .w[data-i]` and changing the highlight is two class toggles, never a re-render. Sentence highlight is the parent `.seg`.

**Scrolling.** When the active segment changes, `scrollIntoView({ block: "center", behavior: "smooth" })` unless the user has scrolled within the last 3 s (a `wheel`/`touchmove` listener sets a cooldown), so reading ahead is not fought by the auto-scroll.

**Drift budget.** Three sources, each bounded: timestamp inaccuracy from Kokoro's duration predictor (tens of ms, within one word); Opus encoder pre-skip (312 samples at 48 kHz = 6.5 ms, corrected by the decoder); time-stretch rounding above 2.0x (scaled timestamps, error < 1 ms). None accumulate across segments because each segment's clock restarts at its own `startAt`. The PRD's gate (< 1 word after 10 minutes) is met by construction; the test is a safeguard against regressions in the backend's timestamp join.

**Click to seek (PLAY-3).** A click on any `.w` span reads its segment id and that word's `start_ms` and issues a seek; the audio for that segment starts from `offset = start_ms / 1000` via `source.start(when, offset)`, so a seek lands on the word, not the sentence.

## Storage (D7)

One SQLite file plus a directory tree; every access pattern in v1 is a lookup by id or a range scan by `(document_id, order)`, so no vector store, no search index and no second database.

**Why not a vector database.** Nothing in v1 asks "which passage is similar to this"; the reader asks "what is segment N" and "what comes after it". Embeddings become relevant only for the PRD's non-goals (chat-with-PDF, semantic jump-to). When that day comes, the `segments` rows are already sentence-sized chunks; embed them into a `segment_embeddings` table with the `sqlite-vec` extension and keep one database.

**DDL**

```sql
CREATE TABLE documents (
  id INTEGER PRIMARY KEY,
  title TEXT NOT NULL,
  filename TEXT NOT NULL,
  sha256 TEXT NOT NULL UNIQUE,            -- dedupe re-uploads
  page_count INTEGER,
  status TEXT NOT NULL CHECK (status IN ('uploaded','parsing','ready','failed')),
  fail_reason TEXT,
  voice_id TEXT, speed REAL,              -- per-document settings, NULL = use global
  position_segment_id INTEGER, position_offset_ms INTEGER DEFAULT 0,
  created_at TEXT NOT NULL, last_opened_at TEXT,
  pages_done INTEGER NOT NULL DEFAULT 0,  -- parse progress, updated every 10 pages + last (added 2026-10-16, migration 0002)
  parse_ms INTEGER,                       -- worker wall time to ready/failed, NULL while parsing (added 2026-10-16, migration 0002)
  acronyms_json TEXT                      -- {ACR: expansion} found at ingestion (ING-6), NULL before re-ingest (added 2026-10-16, migration 0003)
);

CREATE TABLE blocks (
  id INTEGER PRIMARY KEY,
  document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  page INTEGER NOT NULL, "order" INTEGER NOT NULL,
  type TEXT NOT NULL,
  x0 REAL, y0 REAL, x1 REAL, y1 REAL,
  merged_text TEXT NOT NULL
);

CREATE TABLE sections (
  id INTEGER PRIMARY KEY,
  document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  title TEXT NOT NULL, level INTEGER NOT NULL, first_segment_id INTEGER
);

CREATE TABLE segments (
  id INTEGER PRIMARY KEY,
  document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  block_id INTEGER NOT NULL REFERENCES blocks(id),
  section_id INTEGER REFERENCES sections(id),
  "order" INTEGER NOT NULL,
  text TEXT NOT NULL, normalized_text TEXT NOT NULL,
  char_start INTEGER NOT NULL, char_end INTEGER NOT NULL,
  char_map BLOB NOT NULL                  -- packed uint16 array
);
CREATE UNIQUE INDEX segments_doc_order ON segments(document_id, "order");

CREATE TABLE audio_cache (
  segment_id INTEGER NOT NULL REFERENCES segments(id) ON DELETE CASCADE,
  voice_id TEXT NOT NULL, speed REAL NOT NULL, backend TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('ready','failed')),
  path TEXT, duration_ms INTEGER, timestamps_json TEXT,
  created_at TEXT NOT NULL,
  PRIMARY KEY (segment_id, voice_id, speed, backend)
);

CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);  -- default_voice, default_speed
```

**Files**

```
$YOMIKOE_DATA_DIR/
  yomikoe.db
  pdfs/{sha256}.pdf
  audio/{document_id}/{segment_id}/{voice_id}_{speed}.wav    (.ogg with Opus, D16)
```

**Amended 2026-10-16 (D16).** M2 caches WAV (24 kHz, 16-bit mono PCM in a stdlib `wave` container, `audio/wav`, `.wav`): it needs no dependency and every browser's `decodeAudioData` accepts it. Ogg Opus via `opuscodec` (Apache-2.0, in-process; about 7x smaller than WAV) became the default on 2026-10-17 (`audio/ogg`, `.ogg`; the `opus` extra must be installed for it to take effect; `YOMIKOE_AUDIO_FORMAT=wav` selects WAV). The encoder takes the 24 kHz PCM as is (libopus accepts 8/12/16/24/48 kHz input; decoders play at 48 kHz), 48 kbps mono, QEXT off. Without `opuscodec` installed, `default_encoder("opus")` falls back to WAV with a logged warning. There is no ffmpeg anywhere (licence and install cost). The media type is derived from the cached file's extension, so WAV and Opus entries can coexist. Browser decode of Ogg Opus (Safari before 18.4 reportedly fails) was verified in M3 and in the user's own Safari (2026-10-17); no WebM muxer needed. The original plan, kept for reference: Opus in WebM at 48 kHz, 48 kbps mono (a 10 s sentence \~60 KB, a 40-page paper at one voice and speed \~40 MB) via one ffmpeg subprocess per segment.

**Migrations.** Alembic from day one, even for SQLite; the schema will change in M2 and M4 and hand-editing a user's database is not an option.

## Concurrency and process model (D9)

One uvicorn process serves everything; CPU-heavy work goes to two executors chosen by what each library does with the GIL.

| Work | Where | Why |
| --- | --- | --- |
| HTTP + routing | asyncio event loop | FastAPI native; every handler is `async def` and never blocks |
| Ingestion (stages 1–5) | `ProcessPoolExecutor(max_workers=2)` | pdfminer's pure-Python parsing holds the GIL for long stretches and Tesseract is a subprocess anyway; a 300-page parse must not stall the API. Two workers so one slow OCR job does not block a second upload |
| Synthesis | `ThreadPoolExecutor(max_workers=1)` | PyTorch releases the GIL inside its kernels; one thread serializes jobs and owns the single model (D15). A thread, not a process, so the loaded model (300 MB) is not duplicated |
| Encoding (D16) | On the synthesis thread, in process: `WavEncoder` (stdlib) or `OpusEncoder` (`opuscodec`) | No subprocess and no temp files; a 5.75 s sentence encodes to Opus in about 0.1 s |
| SQLite | `aiosqlite`, one connection per request | WAL mode so the ingestion process can write while the API reads |

**Startup.** Load the Kokoro pipeline in the synthesis thread before accepting requests (`lifespan` hook); first load pulls weights from the Hub into `HF_HOME`, later loads take \~2 s. Seed the `voices` list from `backend.voices()`.

**Backpressure.** The synthesis queue is bounded at 16 jobs; an upload's ingestion job is bounded by the process pool. A client that requests a segment far from the current position (a seek) clears the queue, so a user scrubbing through a document cannot pile up stale work.

**Shutdown.** Cancel the queue, wait up to 5 s for the in-flight synthesis, close the pool. A half-written cache file is prevented by writing to `path + ".tmp"` and renaming.

**When this stops being enough.** Multi-user or a GPU box: swap the thread executor for a separate synthesis service behind the same `TTSBackend` interface (a `RemoteBackend` over HTTP), and swap SQLite for Postgres. Nothing in the API layer changes.

## Frontend architecture (D10)

The reader is three components around one explicit player state machine; the machine is the only thing that touches the `AudioContext`, so audio bugs have one place to live.

```
idle --PLAY(seg)--> loading --AUDIO_READY--> playing <--SEGMENT_END (advance)
                       ^                       |   ^
                       |   SEEK / SET_VOICE /  |   |
                       +---SET_SPEED-----------+   |
                       |                    PAUSE  RESUME
                   FETCH_FAILED                |   |
                       v                       v   |
                     error <--FETCH_FAILED-- paused
                       |
                   RETRY / DISMISS --> idle
Dashed/failure edges: FETCH_FAILED. Seek and settings changes pass through loading so the schedule is rebuilt once.
```

**State machine.** `idle → loading → playing ⇄ paused`, with `error` reachable from `loading` and `playing`. Context carried alongside the state: `documentId`, `currentSegmentId`, `voice`, `speed`, `scheduled: Map<segmentId, {source, startAt, duration}>`, `timestamps: Map<segmentId, WordTimestamp[]>`. Every user action and every audio event is an event the machine handles; components dispatch, never call the audio API.

The recommendation is a plain `useReducer` with a typed `(state, event) => state` function and side effects in a single `useEffect` keyed on state, not XState. XState's statecharts (nested states, guards, actors) are more than five states need, and the reducer form keeps the whole machine readable in one file for the coding agent. If the machine grows past \~10 states in M4 (offline queue, export), switching to XState is mechanical because the events are already named.

**Components**

| Component | Owns | Talks to |
| --- | --- | --- |
| `Library` | document list, upload drop zone, progress | `GET/POST /documents` |
| `Reader` | segment list, word spans, active highlight, click-to-seek, TOC sidebar | `GET /documents/{id}/segments`, dispatches `PLAY`/`SEEK` |
| `PlayerBar` | play/pause, skip, voice picker, speed slider, keyboard shortcuts, Media Session hooks | dispatches events, reads state |
| `usePlayer` (hook) | the state machine, `AudioContext`, prefetch loop, highlight rAF loop | `GET /audio/{id}` |

**Data flow.** `Reader` loads segments in pages of 200 as the user scrolls (`IntersectionObserver` on the last rendered segment), so a 300-page document does not render 10,000 spans up front. The player only needs the segment ids in order, which the first page request returns in full as a compact array.

**M5 additions (PLAY-10, PLAY-11, SYN-8, MATH-5; built 2026-10-21).** `LOAD` carries `types` (block type per id) and `blockSpeed` (`{equation}`, default 0.8, 0.5 to 1.0 on a 0.05 grid). New events: `SKIP_EQUATION` (jump to the first segment after the run of consecutive equation segments holding the current one; no-op off an equation) and `REPEAT_EQUATION` (jump to the first segment of that run; off an equation it restarts the current segment); both go through the `SEEK` path, so PLAY-8 skips apply. `SET_BLOCK_SPEED` rebuilds the schedule like `SET_SPEED`; the schedule key is `voice|speed|factor`, and `usePlayer` saves the factor through `PUT /settings` (`equation_speed_factor`) after the settings debounce. `segmentSpeed(type, speed, factors)` (`blockSpeed.ts`) gives an equation clip `speed x factor` rounded to the 0.05 grid and clamped to the speed range, every other type the document speed, so the audio request for an equation is a normal (segment, voice, speed) cache key. Keys `e` and `r` (no modifier held) map to the two events. `chainStart` takes a `pauseSec` (SYN-8, D53) and reports the paused start as `gap: false`, so PLAY-5 accounting does not count a pause as a stall. `PlayerBar` gains Repeat equation and Skip equation buttons (enabled on equations) and an equation-speed select. `Reader` renders each `segments[].math` range (MATH-5, from `segments.math_json` via `decode_math_ranges`) as one `.math` element (boxed when displayed), and the highlight treats an equation segment as one unit (`unitEl`): the whole `.seg` is highlighted while it plays, a maths range in prose as one unit.

**Position persistence (LIB-2).** The hook `PATCH`es `position_segment_id` + `position_offset_ms` every 5 s while playing and on every `PAUSE`, debounced, with `navigator.sendBeacon` on `pagehide` so closing the tab does not lose the last few seconds.

**Keyboard and Media Session (PLAY-6, PLAY-7).** A single `keydown` listener on `document` maps Space, ←, →, `+`, `-` to events; `navigator.mediaSession.setActionHandler` maps play/pause/nexttrack/previoustrack to the same events so lock-screen controls and keys share one path.

**Styling.** Plain CSS modules, no component library; the reader is mostly text and the one hard requirement is a highlight that meets WCAG AA in both themes (`background: var(--hl)` with contrast checked in the fixture page).

**As built in M3 (2026-10-17).** The reducer lives in `web/src/player/machine.ts` (5 states, 17 events, a `generation` counter that makes stale audio events no-ops); the audio side effects live in a `PlayerEngine` class inside `web/src/player/usePlayer.ts`, driven by one effect that rebuilds the schedule whenever the state enters `loading` with a new generation. The "Data flow" paragraph above (pages of 200 on scroll) is not built: M3 loads every segment up front in pages of 500 and renders them all; virtualised rendering is an M4 item with the soak test. Walkthroughs: `docs/CODE_MAP_M3.md`.

## M3 decisions (D20–D25)

**D20, Node without Homebrew.** The frontend needs Node and npm, and the project installs it without Homebrew and without sudo or global tools. `web/scripts/install_node.sh` downloads the Node LTS tarball (v24.22.0, darwin-arm64) and `SHASUMS256.txt` from nodejs.org, verifies the SHA-256, and extracts into `~/.local/node`; `web/scripts/env.sh` puts it on `PATH` and keeps Playwright's browsers in `~/.local/ms-playwright`. Versions are pinned exactly in `package.json` and locked in `package-lock.json`, and `api/scripts/check_licences.py --npm web` applies the licence policy to `node_modules` (production closure react, react-dom, scheduler; `_agent/results/440_licence_npm.txt`). Alternative rejected: Homebrew or nvm, which add a global tool for one runtime.

**D21, Vite proxy, no CORS.** In development the browser talks only to Vite, which proxies `/documents`, `/audio` and `/voices` to the API (`web/vite.config.ts`, `YOMIKOE_API`), so the API needs no CORS middleware and the client builds only relative URLs (`web/src/api/client.ts`). In M4 FastAPI serves the built `web/dist` from the same origin, so production also needs no CORS. Alternative rejected: CORS on the API, which widens the local server's surface for no gain in a single-origin app.

**D22, Chromium asserts the gate.** Headless Chromium runs the playback gate with `--autoplay-policy=no-user-gesture-required`; WebKit and Firefox run the same tests when `YOMIKOE_E2E_ALL_ENGINES=1` is set and are reported, not required, in M3, because headless audio-clock behaviour outside Chromium was untested when the gate was written (the spec's named risk, §8). On 2026-10-17 all three passed 9 of 9 (`_agent/results/436_e2e_chromium_gate.txt`, `437_e2e_webkit.txt`, `438_e2e_firefox.txt`); making WebKit and Firefox required is open for M4.

**D23, settings changes while paused apply at the next Play.** While playing, a voice or speed change restarts the current sentence at the new settings (PLAY-4). While paused or idle, the reducer only updates `voice`/`speed`; `play()` sees that the settings key differs from the one the schedule was built with and dispatches `PLAY` (a fresh schedule from the current sentence) instead of `RESUME`. This avoids fetching and decoding audio the listener may never play while they move the slider. Changes made while a clip is loading are currently ignored (`docs/CODE_MAP_M3.md`, deviation 6).

**D24, pause is `AudioContext.suspend()`.** Suspending the context freezes `currentTime` and every scheduled source together, so resume is sample-exact and the schedule, the prefetched clips and the highlight state are kept. Alternative rejected: stopping sources and rescheduling from the paused offset, which costs a rebuild and risks a click at the restart.

**D25, sections derived client-side.** The `sections` table is never written in M1 or M2 (the phase 1 e2e probe saw 0 sections in every fixture; `_agent/specs/m3-reader-interfaces.md` §7 amendment), so the reader derives sections from segments of type `heading`: each starts a section titled by its text, and `sectionStarts` for `SKIP_SECTION` is their ordered ids (`deriveSections` in `web/src/components/Reader.tsx`). If `GET /documents/{id}` ever returns non-empty `sections`, they are used unchanged. The server-side TOC (ING-8) lands in M4.

## M4 decisions (D26–D30)

D27 is unused: the number was not assigned, and it is left empty so the later numbers stay stable. All four decisions below were proposed by the supervisor in `_agent/specs/m4-library-interfaces.md` and were **confirmed by the user on 2026-10-17**.

**D26, position through `PATCH` with keepalive.** Reading position and per-document settings share one endpoint, `PATCH /documents/{id}` (body keys `position`, `settings`, `opened`, all optional), so there is one server code path for LIB-2 and LIB-3. On `pagehide` the client sends the last known position with `fetch(..., {keepalive: true})`; `navigator.sendBeacon` is not used because it cannot send `PATCH` or a JSON content type without a Blob workaround (`_agent/specs/m4-library-interfaces.md` §1). As built in `web/src/player/usePlayer.ts`, the keepalive `PATCH` goes out only if a position save has already been sent in this visit and the value changed; a debounced settings `PATCH` still waiting at `pagehide` is flushed with keepalive too (`_agent/drafts/m4-2-build-ui.md`, deviation 3). No test exercises the `pagehide` path: it is unverified in a browser. Alternative rejected: `sendBeacon` to a separate `POST` endpoint, a second code path for the same write.

**D28, OCR is Tesseract behind `OCRBackend`.** Stage 1 reports `text_chars` (non-space glyphs) per page; a page with fewer than 20 and a 100 dpi grayscale render whose ink coverage (pixels under 128) is above 0.5 % is sent to `OCRBackend.recognize(page_image)` (`_agent/specs/m4-library-interfaces.md` §3). `TesseractBackend` runs `tesseract --psm 3 tsv` as a subprocess (Apache-2.0, used only if the binary is on PATH); `FakeOCRBackend` returns fixture lines in tests. With no engine the page is left empty and `documents.ocr_skipped_pages` (migration 0004) records the count. On a page sent to OCR, image or figure boxes covering more than 50 % of the page are dropped, because otherwise the scan image typed every recognised line as D12 figure text (`_agent/drafts/m4-3-build-ocr.md`, deviation 2). The backend is wired into `extract_pages` (`_agent/drafts/m4-3-wire-ocr.md`); the ING-2 tests pass 19 with the real-engine test skipped, as tesseract is not installed (`_agent/results/547_ocr_wired.txt`). `ocr_skipped_pages` is not yet exposed through the API (`_agent/drafts/m4-3-build-ocr.md`). Alternative rejected: PaddleOCR (PRD risk table keeps it behind a flag for later).

D28 install note: Tesseract 5.5.3 installed via Homebrew on the dev machine 2026-10-17 (user decision); the real-engine test and the scanned goldens now run (`_agent/results/585`, `600`).

**D29, no virtualisation.** The spec made virtualised rendering conditional on the soak: a windowed `Reader.tsx` only if first render exceeded 5 s or the highlight probes failed (`_agent/specs/m4-library-interfaces.md` §4). The browser soak on the 300-page PDF (6030 segments, all in the DOM) showed the first `.seg` at 619 ms and the last attached at 677 ms, all three probes passing and a restore delta of 0 sentences (`_agent/results/542_soak_browser.txt`); the API soak reached `ready` in 6.89 s with peak RSS 119 MB (process) and 80 MB (children) (`_agent/results/525_soak_api.txt`). So the M3 "load everything" reader stays. Alternative rejected: a window of segments around the current one, code with no measured need.

**D30, one `api` service.** With D21 the API serves the built app from the same origin, so `docker-compose.yml` runs one service, `api`, from a multi-stage `api/Dockerfile` (a Node stage runs `npm ci && npm run build`; the Python stage copies `web/dist`), with the library on the `yomikoe_data` named volume at `/data` (the bind-mount failure seen first on Colima was the same fork race, D9 amendment, `_agent/results/596`; the named volume stays the default for portability and a bind mount is a documented option) and Hugging Face downloads on the `hf_home` volume (`docs/DOCKER.md`). Two departures from the spec, from `_agent/drafts/m4-4-docker.md`: the image installs with `pip install -e ".[tts]"` instead of `pip install .[tts]`, because `yomikoe/storage/migrations` has no `__init__.py` and a wheel install would probably drop the migration files (not tested); and PyTorch comes from the CPU-only index. The server is bound to `0.0.0.0:8765` by the container command. The image was not built here: the dev machine has no container runtime, so gate clause 3 (`docker compose up --build`, then `GET /documents` returns 200 and the app loads at `/`) is run by the user. Alternative rejected: separate `api` and `web` services, which would need CORS or a proxy that D21 already removed.

**D22 update.** In M4 every phase 2 browser spec (library, persist, keys, skip) runs on WebKit and Firefox as well as Chromium: 20 passed on each engine (`_agent/results/543_e2e_chromium_all.txt`, `544_e2e_webkit_all.txt`, `545_e2e_firefox_all.txt`); the soak runs on Chromium only. The gate is still asserted on Chromium only.

**D25 update.** The server side is closed: ingestion writes `sections` rows from heading blocks (ING-8), `level` = 1 for every heading because classification has no heading rank, and segments carry `section_id` (`_agent/drafts/m4-1-build-ing8.md`, `_agent/specs/m4-library-interfaces.md` §1). `yomikoe renormalize` does not rebuild sections, so a document ingested before this change keeps `sections` empty and the client keeps deriving them from heading segments.

**D35, golden floors by fixture class (confirmed).** After the OCR column-order fix, scanned_01/02/03 score 0.98/0.95/0.96 but scanned_04 (0.8868) and scanned_05 (0.8650) fall below 0.95 (`_agent/results/591_golden_scanned_after.txt`). The diagnosis in `_agent/drafts/m4-3-ocr-columns.md` is that 121 of 130 edits in scanned_04 are short substitutions inside inline mathematics, and scanned_05 reads display equations as body text; ordering is correct. "Testing strategy" already says OCR accuracy beyond "produced text for a scanned page" is not tested in v1, so the per-PDF floor for `scanned_*` fixtures is 0.85, while text-layer fixtures keep 0.95 and the mean keeps 0.97. Proposed by the supervisor and confirmed by the user on 2026-10-17 at the M4 close. Alternative rejected: lowering the floor for all fixtures, which would loosen the text-layer gate for no reason.

## M5 and M7 decisions (D36–D40)

M5 "Academic reading" (PRD, Milestones item 5) follows the user's decision of 2026-10-17 that YomiKoe is a study narrator for students and academics, so mathematics is spoken rather than skipped (MATH-1 to MATH-6) and technical vocabulary gets a pronunciation layer (TERM-1 to TERM-5). D36–D39 were proposed by the supervisor and **confirmed by the user on 2026-10-17**; D40 follows a user direction of the same day, with thresholds proposed by the supervisor.

**D36, mathematics is spoken at ingestion.** Equation blocks keep their ING-3 type `equation` and their own segments, so PLAY-10 (skip or repeat an equation), PLAY-11 (equation speed) and MATH-5 (show the page crop from the block bbox) can address them. A new ingestion step after stage 5, "mathspeak", writes the spoken form into `normalized_text`: for equation segments the whole expression, for prose segments the inline-maths spans that stage 3 joined into the sentence (D12), so "where x_i is the i-th sample" becomes "where x sub i is the i-th sample" (MATH-2). Equation numbers and references ("(3)", "Eq. (3)", "Eqs. 3–5") are rewritten in the same step (MATH-4). The step writes `char_map` entries like stage 5's normalization does, so highlighting stays honest: the whole equation (or the whole inline span) maps to its spoken words, and word-level sync inside mathematics is not attempted (MATH-5). The ING-7 cue becomes the fallback output of the same step when an expression cannot be structured: "Equation N" followed by the symbols left to right by name from the MATH-3 table, never silence. The backend is unchanged (SYN-4): it receives words, and TERM-1 pronounces them. Alternative rejected: speaking mathematics inside the TTS backend, which would tie the reading convention to one model and have to be rebuilt for SYN-7.

**D37, structure from the glyphs first.** PDFs do not carry LaTeX source, so the structure of an expression has to be recovered. The first attempt is dependency-free and uses what stage 1 already keeps per glyph: math font names (`CMMI`, `CMSY`, `CMEX`, `MSBM` and the others in the stage 2 equation row), the superscript flag, baseline offsets (sub- and superscripts), stacked bboxes (a fraction is a numerator over a rule over a denominator), and large operators from `CMEX` (∑ ∏ ∫ with limits above and below). An image-to-LaTeX model is a later option behind a flag, and only if its code and weights are licence-clean under the project rule; the survey in `_agent/research/m5-math-speech-options.md` decides which, if any. The scanned path (no glyphs) uses the MATH-1 fallback until MATH-6. Alternative rejected: requiring LaTeX source, which PDFs do not carry.

D37 survey result (2026-10-17, confirmed by the user on 2026-10-17; `_agent/research/m5-math-speech-options.md`, licence evidence `_agent/results/607_math_speech_licences.md`): own rule engine over glyphs first; MathCAT (MIT) or Speech Rule Engine (Apache-2.0, needs Node) as an optional MathML layer later; for scanned pages only the Pix2Text MFR weights (MIT on Hugging Face) or UniMERNet (Apache-2.0 code, weights licence unverified) are candidates; excluded: Nougat weights (CC-BY-NC), pix2tex weights (reported CC BY-NC-SA, unverified) and the pix2text package (AGPL-3.0 via doclayout-yolo).

**D38, the board is a rendered page plus an overlay (M7, VIEW-1 to VIEW-3; numbered M6 until 2026-10-19).** Proposed by the supervisor and confirmed by the user on 2026-10-17. Pages are rendered server-side by pypdfium2 (already a dependency for OCR rendering, ING-2; its licence is already in the suite, `api/scripts/check_licences.py`) at a fixed dpi and cached under the data dir next to the audio cache. Ingestion stores word boxes (today a `blocks` row keeps one bbox, that of `source[0]`, and word boxes are not kept; `docs/CODE_MAP_M1.md`), so a highlighted word and an equation box can be drawn over the image. The reader's board is a second renderer of the same player state (D10): segment id plus offset selects a page and a box, so the player state machine does not change. Alternative noted, not rejected yet: pdf.js in the browser (Apache-2.0) with the server shipping only boxes; decided in the M7 spec.

**D39, annotations are segment-anchored (M7, NOTE-1 to NOTE-5; numbered M6 until 2026-10-19).** Proposed by the supervisor and confirmed by the user on 2026-10-17. Highlights, notes and bookmarks go in one `annotations` table, added through an Alembic migration, keyed by document and anchored by segment id plus character offsets: the coordinates the player and the reader already use (see "Segment model"), so both the text view and the board (D38) can draw them and a note click seeks through the existing player action (PLAY-3). They stay local with the library, no accounts and no sync. Consequence: segment ids are not stable across re-ingestion (D7), so a re-ingested document loses its annotations unless they are re-anchored by text match; whether and how to re-anchor is an open question in the PRD. Alternative not chosen: anchoring by page and PDF coordinates, which would not survive a change of text-view layout and would not serve non-PDF sources (M8).

**D40, the document profile gates the speech rules (M5, ING-11).** User direction 2026-10-17; thresholds proposed by the supervisor and open to tuning on the fixtures. The same characters mean different things by document: in an ordinary text PDF "[12]" is a citation and is dropped (ING-6), while in a mathematics document "[0, 1]" is an interval and a bracket stack is a matrix, and both must be read. So one profile pass over the merged blocks, between stage 4 (merge) and stage 5 (segment) because stage 5's normalizer already needs the class for the bracket rule, computes a profile: the share of equation blocks and inline-maths spans by character mass, the code-listing share (ING-10), the citation style (numeric brackets, author–year, none) and the scanned-page share (ING-2), plus a class. It is stored in a new `documents.profile_json` column (Alembic migration) with the raw shares and the class. Proposed thresholds: `math` when equation plus inline-maths mass is ≥ 15 % of characters or there is ≥ 1 display equation per page on average; `prose` when that mass is under 2 % and there are no display equations; `mixed` otherwise. Tuned on the 30 gate (e) fixtures in phase 2 (2026-10-17; these thresholds matched 17 of 30, the tuned ones 28 of 30, `_agent/results/677` and `681`): a display equation is a run of consecutive equation blocks and `math` needs ≥ 2 per page; ≥ 4 % of prose tokens carrying a maths glyph also makes `math` (textbook pages set formulas inline, with no equation block); `prose` is mass under 1 %, under 1 display per page and code share under 10 % (monospace glyph share until ING-10's `code` blocks exist); until MATH-2's maths spans land, inline mass is estimated from those maths-glyph tokens. In `prose`, bracketed numbers are citations and are dropped; in `math`, brackets inside a maths span are read as intervals or matrices and only bracket groups outside maths with citation shape are dropped; in `mixed` the rule is per span. The normalizer and mathspeak (D36) receive the profile as a parameter, with no global state, so the eval runner can run a fixture under each class. A user override of the class (LIB-1 badge) re-normalizes through the existing `yomikoe renormalize` path without re-ingesting. A bracket group whose first number starts with 0 is an interval under every profile (ING-6 rule, 5b09a5f); the profile gates only citation-shaped groups. Alternative rejected: a per-sentence guess with no document context, which cannot tell "[12]" from "[0, 1]" in a paper that uses both.

## M6 decisions (D45–D51; D52 and D53 follow the same table)

M6 "Domain reading" (PRD, Milestones item 6) follows the user's decision of 2026-10-19 to accept every recommendation of `docs/PRD_DOMAINS.md`, including its placement as an own milestone after M5 (that PRD's decision 29); Classroom view moved to M7 and Sources and formats to M8. The rules hook into existing stages (ING-6 normalizer, MATH-3 symbol table, mathspeak, ING-11 profile, SYN-4, TERM-1 and TERM-4, sentence splitting, ING-3 and ING-10, the eval layer); nothing changes in synthesis, audio delivery (D5) or the player (D10). The decisions are copied from `docs/PRD_DOMAINS.md`, "Architecture and stack"; the argument and the per-domain conventions live there.

| # | Decision | Choice | Status |
| --- | --- | --- | --- |
| D45 | Profile fields | ING-11 profile gains a multi-valued `fields` set beside the `prose`/`mixed`/`math` class, detected from token densities, user-overridable, re-normalizing without re-ingesting (DOM-22) | Confirmed 2026-10-19 (user) |
| D46 | One wording per symbol per role | `math_convention.json` entries may carry role-keyed wordings selected by operand class or span type; banned wordings stay banned in every role | Confirmed 2026-10-19 (user) |
| D47 | Units as expressions | Units are parsed as expressions (prefix, unit, power, product, quotient), not token by token; "per" is the units reading of `/`, "over" the maths reading (DOM-1) | Confirmed 2026-10-19 (user) |
| D48 | Shared data tables | Shared data tables in one place under `api/yomikoe/ingestion/` (element symbols and names, polyatomic ions, units and prefixes, currencies, per-field abbreviations, reference works), each a data file with its own unit tests; no table is duplicated per field | Confirmed 2026-10-19 (user) |
| D49 | Normalization order | Inside normalization: (1) sentence-split protections for abbreviation dots; (2) whole-token tables (references, citations, tickers, gene symbols, `y/y`, `n/m`, HGVS); (3) number-anchored grammar (currency, units, scientific notation, uncertainty, ranges, ratios, data units, coordinates); (4) field-gated rules (formulas, regnal numerals, clinical shorthand, statistics position); (5) today's `_speak_symbols` and mathspeak with role-keyed entries; (6) SYN-4 and the lexicon in the backend | Confirmed 2026-10-19 (user) |
| D50 | EVAL-11 | EVAL-11 with per-domain floors, tier 0, same scorer as EVAL-10 (DOM-27) | Confirmed 2026-10-19 (user) |
| D51 | Per-document reading settings | Per-document reading settings (`jurisdiction`, `read_quantity_names`, `read_tables`, `quote_marks`) stored with the document like the ING-11 override (DOM-23) | Confirmed 2026-10-19 (user) |
| D52 | Rename to Yomikoe | Product renamed from HearNarro to YomiKoe (2026-10-21): wordmark YomiKoe, identifiers `yomikoe`, env prefix `YOMIKOE_`, domains per the PRD "Domains" table: yomikoe.app brand and landing page, app.yomikoe.app reader, api.yomikoe.app API, getyomikoe.com a 301 redirect that is never printed; hosting is M9, the final milestone (decided 2026-10-21), legacy `hearnarro.db` auto-moved, `_agent/` evidence left as-is (formerly HearNarro) | Confirmed 2026-10-21 (user) |
| D53 | SYN-8 pauses | Pauses are client-side start-time gaps in the web scheduler (`chainStart`), keyed by the segment's block type: heading 600 ms, list 250 ms, equation 400 ms (`web/src/player/pauses.ts`). The pause is real time, not stretched by speed. The synthesis service and the audio cache are untouched: the cache stays keyed by segment, voice and speed (D6), so a preset such as VIEW-4 classroom can change lengths without re-synthesis. Decided by the supervisor 2026-10-17 as spec Q7, built 2026-10-21 (M5 phase 5) | Open to the user's confirmation |
| D54 | Landing page hosting | yomikoe.app is served by GitHub Pages from `site/` via `.github/workflows/site.yml` (public repo, free, HTTPS by Let's Encrypt, no server to run); app. and api. hosting is decided at phase 2; getyomikoe.com is a registrar/Cloudflare 301 rule | Proposed 2026-10-21, awaiting user confirmation |

## Testing strategy (D11)

Four kinds of test, each tied to a milestone gate; the gate tests are written before the code they gate, and CI runs everything but the benchmark on every push.

| Kind | What it checks | Fixture | Gate |
| --- | --- | --- | --- |
| Reading-order golden | Stage 3 output vs `name.expected.jsonl` for each of 20 PDFs; prose-only (D12): both sides keep only heading, body, list, caption and footnote segments; word-level (D14): the prose texts are joined with single spaces, lowercased, split on whitespace, ASCII and typographic punctuation stripped from each token and empty tokens dropped; score = 1 − (word-sequence Levenshtein distance / expected word count); assert ≥ 0.95 per PDF and ≥ 0.97 mean, and per PDF the excluded character mass (chars in table/equation segments ÷ chars in all segments) agrees within 0.05 absolute on each side. The sentence-level score (segment texts compared whole) is printed per PDF as a diagnostic and never asserted; sentence boundaries are covered by the stage-5 unit tests | `api/tests/fixtures/pdfs/` | M1 |
| Document quality checklist | every document, 11 checks with thresholds | fixtures + any PDF | M1 |
| Stage unit tests | Each ingestion stage on hand-made inputs: column split on synthetic bboxes, header detection on a 5-page repeat, de-hyphenation cases, pysbd offsets round-trip, normalizer `char_map` invariants | Inline in tests | M1 |
| Sentence boundaries | P/R/F1 of parser sentence boundaries vs `<stem>.sentences.txt` over the aligned word stream; F1 ≥ 0.90 and R ≥ 0.97 per fixture, mean F1 ≥ 0.95 (D18) | 15 text fixtures | M2 |
| Timestamp invariants | For every synthesized segment: timestamps sorted, non-overlapping, last `end_ms` ≤ `duration_ms`, every `(char_start, char_end)` maps into `text` through `char_map`; after stretch, scaled timestamps keep the same invariants | 50 sentences from the fixtures, a `FakeBackend` for speed | M2 |
| API contract | Each endpoint via `httpx.AsyncClient` against a temp SQLite: upload → parsing → ready; segments paging; `/audio` cache miss then hit; `PATCH` position round-trip | `FakeBackend` returning silence with synthetic timestamps | M2 |
| Playback (browser) | Playwright: load a 30-segment fixture, play 20 s, assert the highlighted word matches the expected word at three probe times; seek by click; change speed mid-play | Vite dev server + API with `FakeBackend` | M3 |
| Benchmark | `scripts/bench.py`: time-to-first-audio and real-time factor for Kokoro on this machine, 20 sentences, printed as a table and written to `bench/<date>.json` | Real backend | M2, M4 |
| Soak | 300-page PDF, play at 2x for 10 minutes with `FakeBackend`, assert no error state, memory growth < 50 MB | Generated PDF | M4 |
| Evals (EVAL-1 to EVAL-9, D31) | The same scorers without thresholds, every per-example score kept in a run record and compared with a baseline; the trend line above the gates, never a failure | Fixtures, `evals/data/`, 50 fixture sentences, a human rubric | None (report only; D33) |

**Making the ground truth.** Run stage 3 on each fixture, dump the segment order, hand-correct it once in an editor, commit as `expected.jsonl`. It is tedious for 20 PDFs (roughly a morning) and it is the single most valuable artifact in the repo: every later change to the parser is measured against it. Mark which five fixtures exercise two-column layout so the score can be reported per class.

**`FakeBackend`.** Implements `TTSBackend`, returns 80 ms of silence per word with evenly spaced timestamps and no model download. Every test above M2's benchmark uses it, so CI needs no GPU, no Hub access and runs in under a minute. The real Kokoro backend has one smoke test, marked `@pytest.mark.model`, skipped unless `YOMIKOE_TEST_MODEL=1`.

**What is not tested in v1.** Audio quality (subjective; the benchmark prints a path to listen to), OCR accuracy beyond "produced text for a scanned page", and iOS background playback (manual check in M3). None of these is gated; from 2026-10-17 the first two are measured by evals rather than tests: intelligibility and timestamp sync by EVAL-5 and EVAL-6, OCR accuracy by EVAL-8 (character error rate, once tesseract is installed), and listening quality by the EVAL-9 human rubric.

## Eval layer (D31–D34)

Gates answer "is it good enough?"; evals answer "how good, and better or worse than last time?". The scores already computed by the gate tests were reduced to pass/fail and lost, so a fixture could drift from 0.99 to 0.96 inside a 0.95 floor unseen (EVAL-1). The loop:

```
dataset ──► system under test (at a commit, with a config) ──► output ──► scorer
   ──► per-example scores ──► run record (JSON) ──► compare with baseline ──► scorecard
                                                    (mean, worst, Δ per example, regressions flagged)
```

Record shape, one file per run under `evals/runs/` (D32):

```json
{"run_id":"2026-10-17_7f2f015","commit":"7f2f015","date":"2026-10-17T14:02:00Z",
 "config":{"backend":"fake","speed":1.0,"tesseract":false},
 "suites":{"EVAL-1":{"examples":[{"id":"arxiv_2401_01234","class":"academic","score":0.993}],
                      "aggregate":{"mean":0.991,"min":0.962,"by_class":{"academic":0.988}}}}}
```

Run with `api/.venv/bin/python -m yomikoe.evals run all --tier 0` before and after a parser or normalizer change, `--tier 1` when touching synthesis or swapping a backend; a full tier 0 + 1 run is recorded at each milestone close, and a backend swap runs EVAL-5/6/7 once per backend on identical sentences.

| Phase | Deliverable | Acceptance |
| --- | --- | --- |
| E0 Runner + store | Runner, store, EVAL-1 and EVAL-2 wrapped | One run record written; `compare` of two identical runs shows zero deltas |
| E1 Fast suites | EVAL-3, EVAL-4 with its ~300-pair dataset | Tier 0 completes under 60 s; per-category accuracy printed |
| E2 Model suites | EVAL-5, EVAL-6, EVAL-7 under `YOMIKOE_TEST_MODEL=1`; ASR dependency through the licence check | One tier-1 record on this machine; WER and sync offset per speed |
| E3 Reporting | Markdown + HTML scorecard; baseline rule in CLAUDE.md | Scorecard linked from a milestone guide |
| E4 Human + OCR | EVAL-9 rubric and ingestion; EVAL-8 once tesseract is present | One listening session recorded |

Full design and rationale: `_agent/specs/evals-design.md`.

## Decisions needed before M1

All three were decided on 2026-10-15 as recommended; the rest of the doc stands on the PRD's constraints and can be changed later without unwinding anything.

- [ ] **D5 — Audio delivery.** Accept per-segment HTTP + Web Audio scheduling, replacing the PRD's WebSocket + MSE? If yes, I update the PRD (remove `/play` WebSocket, change two stack rows) and `docs/PRD.md` in the repo.
- [ ] **D7 — Cache format.** Decided 2026-10-15 as Opus at 48 kbps; amended 2026-10-16 by D16: Ogg Opus in process via `opuscodec`, no external encoder. Decided 2026-10-17: Ogg Opus is the default (clean play in the user's Safari).
- [ ] **D10 — Player state.** Plain `useReducer` state machine now, XState only if it grows past \~10 states. The alternative is XState from day one for the visualizer and test tooling, at the cost of a dependency and a learning curve for the coding agent.

Open but not blocking:

- [ ] Two-column detection threshold (8% of page width) and the full-width cutoff (60%) are guesses; the fixture set will tune them in M1.
- [ ] Whether to ship Marker behind the flag in v1 at all, given its GPL license sits oddly next to an Apache project. Decide after seeing how the geometric parser scores on the five academic fixtures.
- [ ] iOS background playback workaround (muted `<audio>` element fed from Web Audio): spike in M3, drop if it does not work in a day.
