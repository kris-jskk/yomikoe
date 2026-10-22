# PRD: YomiKoe

As of 2026-10-15 · Sowmya

## Overview

YomiKoe (formerly HearNarro, renamed 2026-10-21) is a Speechify-style reader: drop in a PDF, pick a voice and a speed, and listen with the text highlighted as it plays. v1 is a self-hosted web app backed by open TTS models, built so the synthesis engine can be swapped without touching the reader.

The problem it solves: long documents (papers, reports, textbooks) are easier to consume as audio while walking, driving or doing chores, but generic PDF-to-audio tools mangle layout, read footnotes mid-sentence, and sound flat. Commercial products (Speechify, Natural Reader) solve this well but are subscription-gated, closed, and run on their own voices.

Vision in one line: an open, extensible reading engine where the hard part is text extraction and playback plumbing, and the voice is a pluggable backend.

Focus decided 2026-10-17 (user): YomiKoe is a study narrator. It takes a PDF (a paper, a textbook chapter, lecture notes) and narrates it for students and people in academia, and it serves three usage modes on one engine: the student learning (the main focus), the technical learner working through a technical book, and the book listener following a printed book while listening (see "Usage modes" below), so formulas are spoken as a person would read them aloud rather than skipped, and technical vocabulary is pronounced correctly. That work is milestone M5 "Academic reading" (MATH and TERM requirements below); M1 to M4 stay as built.

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
- Non-PDF formats (EPUB, DOCX, web pages); keep the ingestion interface open for them (revisited 2026-10-17: SRC-1 to SRC-4, M8; numbered M7 until 2026-10-19; web pages read through the browser extension are M10, decided 2026-10-22, `docs/PRD_EXTENSION.md`)

**Success metrics**

| Metric | Target | How measured |
| --- | --- | --- |
| Reading-order accuracy on a 20-PDF test set | 95% of sentences in correct order | Manual review against ground truth |
| Time to first audio (50-page PDF, CPU) | < 2 s | Instrumented in the API |
| Real-time factor, Kokoro on CPU | < 0.3 (3x faster than playback) | Benchmark script |
| Highlight drift after 10 minutes of playback | < 1 word | Manual check on 5 documents |
| Crash-free playback of a 300-page PDF | 100% | Soak test |

Evals (EVAL-1 to EVAL-9, decided 2026-10-17, EVAL-10 for M5 and EVAL-11 for M6, added 2026-10-19; EVAL-12 for M10, proposed 2026-10-22; Technical Design D31–D34, D50) produce the trend line for these metrics and for quality the gates do not measure: every run keeps its per-example scores in a committed record so two commits can be compared. The gate tests remain the floor and the only thing that blocks a merge.

## Users and use cases

The first user is you: a technical reader working through long papers and reports who wants to listen while away from the screen. Design for that person first; the other personas below shape the interface but do not gate v1.

From 2026-10-17 (user decision, M5) the primary users are students and academic readers: people studying from papers, textbooks and lecture notes, where equations, symbols, units and domain terms are a large share of the text. The accessibility user stays secondary; the commuter folds into the book listener (2026-10-17).

**Usage modes** (added 2026-10-17, user direction). The app is used in three ways. The three modes share one engine and differ in the VIEW-4 preset and in which block types are read: the "classroom" preset serves the student, a "study" preset serves the technical learner (code listings read or cued, ING-10; notes on), and a "listen" preset serves the book listener (no extra pauses; captions and footnotes muted by default via PLAY-8).

| Mode | What it is for | What matters | Preset (VIEW-4) |
| --- | --- | --- | --- |
| Student (main focus) | Study from notes, textbooks and papers | Board view, classroom pacing, notes and highlights, spoken maths | classroom |
| Technical learner | Learn from technical books and papers | Code listings, identifiers and acronyms read well, equations, notes, 1.5–2x | study |
| Book listener | Narration with the printed book in hand | Natural pacing, chapter navigation, resume; no pauses or pointer; the board optional | listen |

| Persona | Core need | What they do in the app |
| --- | --- | --- |
| Academic reader and technical learner (primary) | Get through a 40-page paper or a technical book chapter, equations and code included, to learn from it | Upload, pick a voice, play at 1.5–2x, skip the references section, hear each formula read aloud, hear code listings cued or read, take notes |
| Student (primary) | Study a textbook chapter or lecture notes, scanned or born-digital | Upload the PDF (OCR for photographed pages), follow the highlight, slow down or repeat an equation, fix a mispronounced term |
| Accessibility user (dyslexia, low vision) | Read any document comfortably | Larger highlight, slower speed, keyboard-only control |
| Book listener (primary; absorbs the commuter, 2026-10-17) | Listen to a book while following in the printed copy, or hands-free | Resume where they left off, chapter navigation, natural pacing with no extra pauses, background playback on phone browser |

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
| ING-3 | P0 | Extract text as structured blocks with type: heading, body, caption, footnote, header/footer, table, equation, list item, code (ING-10, added 2026-10-17); figure-internal text is typed figure and never read (D12) |
| ING-4 | P0 | Produce a linear reading order that handles two-column layouts and excludes header/footer/page-number blocks |
| ING-5 | P0 | Join hyphenated line breaks and merge lines into sentences; split into sentence-level segments with character offsets back to the source block. A bulleted or numbered list item (any common bullet glyph, arrows included) is its own segment, never joined with the next item into one sentence; a glyph bullet is shown but not spoken |
| ING-6 | P1 | Normalize text for speech: numbers, currency, dates, URLs → domain spoken with dot ("shopping dot com", e-mail "name at host dot com"), citations like \[12\], common abbreviations; acronym pronunciation decided in the backend with a lexicon and overrides, in context: a collocation ("TED talk") or the document's own definition ("Transferable Erosion Deposit (TED)", stored per document at ingestion) changes the reading |
| ING-7 | P1 | Tables read as row-by-row prose with a spoken cue ("Table 2, 3 rows"); equations read as a cue ("equation") not symbol soup |
| ING-8 | P1 | Build a table of contents from headings for navigation |
| ING-9 | P2 | Ingestion interface accepts EPUB, DOCX, HTML through the same block schema; see SRC-1, promoted 2026-10-17 |
| ING-10 | P1 | Code listings (monospace font runs, indented blocks with code punctuation) are typed `code` at ingestion (extends ING-3); by default spoken as a cue "Code listing, N lines" and shown on the board (VIEW-1), with a toggle to read the code line by line through TERM-5's identifier rules; inline code spans inside a sentence are read as their words (added 2026-10-17) |
| ING-11 | P0 | Document profile (M5, added 2026-10-17, D40): after ingestion a profile is computed and stored: share of equation blocks and inline-maths spans by character mass, code-listing share (ING-10), citation style (numeric brackets, author–year, none), scanned-page share (ING-2), and a class from thresholds: `prose`, `mixed`, `math`. Normalization (ING-6), mathspeak (MATH-1, MATH-2), citation handling (TERM-3) and the mode preset default (VIEW-4) read the profile: in `prose`, bracketed numbers are citations and are dropped; in `math`, brackets inside a maths span are read as intervals or matrices and only bracket groups outside maths with citation shape are dropped; in `mixed`, per span: a bracket group inside a maths span follows the maths rule, elsewhere the prose rule. The profile is shown in the library row (LIB-1, a small badge) and the user can override the class per document; an override re-normalizes without re-ingesting (the existing `yomikoe renormalize` path). A bracket group whose first number starts with 0 is an interval under every profile (ING-6 rule, 5b09a5f); the profile gates only citation-shaped groups |

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
| SYN-8 | P1 (pause), P2 (pitch) | Content-aware delivery: pause length and pitch differ for headings, captions, body text. Raised 2026-10-17 (M5): pause length for headings, theorem-style openers and list items is P1; pitch stays P2. Built in M5 as client-side pause gaps (D53), pitch still P2 |
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
| PLAY-10 | P1 | Skip or repeat the current equation with one action (keyboard and button), independent of sentence skip (added 2026-10-17, M5); built 2026-10-21 (M5 phase 5) |
| PLAY-11 | P1 | Per-block-type speed: equation segments play at a configurable fraction of the document speed (default 0.8×), captions and footnotes at the document speed (added 2026-10-17, M5); built 2026-10-21 (M5 phase 5) |

**Library (LIB)**

| ID | Pri | Requirement |
| --- | --- | --- |
| LIB-1 | P0 | List of uploaded documents with title, page count, progress percent, last opened |
| LIB-2 | P0 | Reading position (segment id + offset) saved every 5 seconds and on pause |
| LIB-3 | P0 | Per-document voice and speed remembered; a global default for new documents |
| LIB-4 | P1 | Delete a document and its cached audio |
| LIB-5 | P2 | Folders or tags |

**Spoken mathematics (MATH)**

Added 2026-10-17 (M5, Technical Design D36–D37, confirmed by the user 2026-10-17). Mathematics is spoken as English words at ingestion; the backend receives words (SYN-4).

| ID | Pri | Requirement |
| --- | --- | --- |
| MATH-1 | P0 | A display equation block (ING-3 type equation) is spoken as English in a standard reading convention (ClearSpeak or MathSpeak style): operators, relations, Greek letters, fractions, powers, roots, subscripts, sums, products and integrals with their limits. The one-word cue of ING-7 becomes the fallback, used only when the expression cannot be structured; the fallback then reads "Equation N" (its number if present) followed by the symbols left to right by name, never silence and never symbol soup. Outside maths spans, and in any document before mathspeak, a second normalizer pass (`_speak_symbols` in `api/yomikoe/ingestion/normalize.py`, table in `api/yomikoe/ingestion/math_symbols.py`, added 2026-10-17 in 796de80) reads mathematical symbols and Greek letters by name ("ν > 0" → "nu greater than 0") and a lone letter glued to "(" as function application ("O(1)" → "O of (1)") |
| MATH-2 | P0 | Inline mathematics inside a sentence (joined by stage 3, D12) is spoken in place with the same rules, so "where x_i is the i-th sample" reads as "where x sub i is the i-th sample" |
| MATH-3 | P0 | A symbol-to-words table covers Greek letters, mathematical operators and relations (at least ≤ ≥ ≈ ≠ ± × ÷ · ∂ ∇ ∞ ∈ ∉ ⊂ ∑ ∏ ∫ √ → ⇒ ∀ ∃ ¬ ∧ ∨), units and SI prefixes (km, ms, μm, kHz, MPa, mol; °C already handled by ING-6), and chemical formulas (H2O, CO2, CH4 spoken letter by letter with numbers), so no symbol reaches the voice as an unknown word |
| MATH-4 | P1 | Equation numbers and references: a display equation's "(3)" is spoken as "equation 3" before the equation; "Eq. (3)", "Eqs. 3–5" and "Equation (3)" in prose become "equation 3" and "equations 3 to 5"; "Theorem 2.1", "Lemma 3", "Definition", "Proof" and "Corollary" openers are spoken with a short pause after them |
| MATH-5 | P1 | While an equation segment plays, the reader highlights the whole segment (sentence-level) and shows the equation as it appears on the page, shown and boxed on the board (VIEW-2; was "a rendered crop from the stored block bbox", changed 2026-10-17); word-level sync inside mathematics is not required. M5 ships the sentence-level highlight with maths ranges boxed in the reader text; the board crop is VIEW-2 (M7) |
| MATH-6 | P2 | Scanned pages: mathematics recovered from the page image (equation image to structure) behind an interface like `OCRBackend` (D28); until then OCR'd equations use the MATH-1 fallback |

**Technical vocabulary (TERM)**

Added 2026-10-17 (M5). Extends the pronunciation layer the Kokoro backend already has (`api/yomikoe/synthesis/acronyms.py`, `api/yomikoe/synthesis/lexicon_overrides.py`).

| ID | Pri | Requirement |
| --- | --- | --- |
| TERM-1 | P0 | A shipped academic pronunciation lexicon (mathematics, statistics, physics, chemistry, biology, computer science, Latin and Greek loanwords, common surnames in citations) consulted before the backend's general lexicon, with EVAL-4 categories for each domain. Built 2026-10-20, phase 4: the lexicon sits under the hand overrides (SYN-4) and the user's respellings (TERM-2): user respelling > hand overrides > academic lexicon > the backend's lexicon |
| TERM-2 | P0 | Per-document pronunciation overrides the user sets in the reader (select a word, "pronounce as", type a respelling or pick from suggestions), stored with the document and applied by the backend; plus a global user lexicon that applies to every document. Changing an override invalidates the cached audio of affected segments (SYN-6 keys stay by segment id; the override version joins the key or the cache is purged for those segments). Built 2026-10-20, phase 4: the cache is purged; a change deletes the cache rows and audio files of every segment of the affected document (every document for a global change) whose normalized text holds the word as a whole token, case-insensitive, and returns that count; SYN-6 keys are unchanged. Suggestions are not built in M5 |
| TERM-3 | P1 | Citations: numeric clusters "[12, 14]" stay dropped (ING-6); author–year citations "(Smith et al., 2019)" are spoken as "Smith et al. 2019" or skipped, by a PLAY-8-style toggle; "et al." is spoken "et al" (already); a surname before "et al." is pronounced through TERM-1. Built 2026-10-20, phase 4: the toggle is the document setting `profile.author_year_citations` (`read` by default, `skip`), which re-normalizes (a citation is inside a sentence and the player skips whole segments); the narrative form "Smith et al. (2019)" is not matched yet |
| TERM-4 | P1 | Academic abbreviations spoken by expansion: i.e., e.g., cf., w.r.t., resp., s.t., iff, w.l.o.g., viz., et seq., ibid., op. cit.; the expansion table is configurable. Built 2026-10-20, phase 4: "configurable" is the one expansion table in the code; a user-editable copy is not built in M5 |
| TERM-5 | P2 | Code identifiers and file names in computer-science papers (snake_case, camelCase, dotted.paths) spoken as their words |

**Domain notation (DOM)**

Added 2026-10-19 (user decision: the narrator reads the notation of chemistry, physics, biology and medicine, finance and economics, history and law, computer science and statistics as a teacher would). DOM-1 to DOM-27 are specified in `docs/PRD_DOMAINS.md`, not repeated here; they extend MATH-3, TERM-1 and TERM-4 above and are scheduled as M6 Domain reading (Technical Design D45–D51, confirmed by the user 2026-10-19).

**Sources (SRC)**

Added 2026-10-17 (user direction: read the books and documents the user already has in other apps). Proposed for M8, after M7 Classroom view; not M5 scope (renumbered from M6 2026-10-17, and from M7 to M8 on 2026-10-19 when M6 Domain reading was placed).

| ID | Pri | Requirement |
| --- | --- | --- |
| SRC-1 | P1 | Import EPUB, DOCX, HTML, Markdown and plain text through the same block schema as PDF (promotes ING-9 from P2 to P1). HTML and plain text land in M10 (EXT-15, posted by the browser extension, `docs/PRD_EXTENSION.md`); EPUB/DOCX/Markdown stay in M8 |
| SRC-2 | P1 | Import several files at once by drag-drop or folder pick, and on macOS read the local Apple Books library folder for DRM-free books (sideloaded EPUB and PDF only) |
| SRC-3 | P2 | Cloud sources (iCloud Drive, Google Drive, Dropbox) through their file pickers or APIs; the Files app on iOS through the standard picker |
| SRC-4 | P2 | Kindle: narrate what Amazon exposes to the user, the notes and highlights export ("My Clippings.txt" and the notebook export), not the books |

DRM boundary: purchased Kindle titles and purchased Apple Books titles are encrypted (Amazon has no content API; Apple uses FairPlay). YomiKoe never removes DRM, so those titles are out of scope in every milestone.

**Classroom view (VIEW)**

Added 2026-10-17 (user direction: a student learns as in a real classroom, where the teacher, the narrator, teaches from printed notes, a textbook or the board, and the student sees exactly what is being taught). Proposed for M7, after M6 Domain reading (renumbered from M6 2026-10-19; Technical Design D38, confirmed by the user 2026-10-17).

| ID | Pri | Requirement |
| --- | --- | --- |
| VIEW-1 | P0 | Board view: the reader can show the rendered page image (the "board") instead of, or beside, the extracted text; the current sentence and word are highlighted on the page image from boxes stored at ingestion; the board turns to the page of the segment being spoken, so the student always sees what is being read. Today a block stores one bbox (the `blocks` row stores the bbox of `source[0]`, `docs/CODE_MAP_M1.md`) and word boxes are not stored, so ingestion must keep word boxes |
| VIEW-2 | P0 | Pointer: on the board a pointer or underline moves with the narration, like a teacher's finger on the page; an equation segment is boxed whole while it is spoken |
| VIEW-3 | P1 | Figures and tables are shown when discussed: when a caption is read, the pointer boxes the figure or table; a "Figure 3" or "Table 2" reference in prose can turn the board to it and back (toggle, default on in classroom mode). Figure-internal text stays unread (ING-3, D12) |
| VIEW-4 | P1 | Mode presets, three presets: classroom, study, listen ("Usage modes", 2026-10-17). Classroom mode preset: pauses after definitions, theorem statements and equations (SYN-8 pause part), repeat the current sentence or equation (PLAY-10), slower equations (PLAY-11), board view on; one switch turns them all on |
| VIEW-5 | P2 | Phone layout for the board: pinch zoom with the pointer kept in view; lock-screen controls (PLAY-7) |

The narrator reads and paces the author's own text. It does not explain, summarize or answer questions; the "Summaries, chat-with-PDF" non-goal stands until the user decides otherwise (open question below).

**Study tools (NOTE)**

Added 2026-10-17 (user direction: in the classroom the student can pause, take notes and highlight; pause already exists, PLAY-1, D24). Proposed for M7 with VIEW (renumbered from M6 2026-10-19; Technical Design D39, confirmed by the user 2026-10-17).

| ID | Pri | Requirement |
| --- | --- | --- |
| NOTE-1 | P0 | Highlight a passage, by selecting text in the text view or dragging on the board, stored per document as segment id plus character offsets (the same coordinates the player uses, see Technical Design "Segment model"), shown in both views, removable |
| NOTE-2 | P0 | Notes: while paused (or without pausing), type a note attached to the current segment or to a highlight; stored with the document; a notes panel lists them in reading order and clicking one seeks there (PLAY-3) |
| NOTE-3 | P1 | Bookmarks: mark the current position with one key; the library (LIB-1) shows the count; jump between bookmarks |
| NOTE-4 | P1 | Export highlights, notes and bookmarks as Markdown with page numbers and the quoted text; import back is not required |
| NOTE-5 | P2 | Review mode: play only the highlighted passages of a document, in order |

Notes and highlights are the student's own data and stay local with the library: no accounts, no sync; the multi-user non-goal stands.

**Evals (EVAL)**

Added 2026-10-17 (Technical Design D31–D34). An eval runs the system over a fixed dataset, scores every example and records the scores against the commit; it has no threshold and never fails a build. Tier 0 needs no model (seconds), tier 1 needs Kokoro or another tool on CPU (minutes, on demand), tier 2 is a human session. The ING/SYN/PLAY/LIB IDs in parentheses are what each eval measures.

| ID | Requirement | Dataset | Scorer | Tier |
| --- | --- | --- | --- | --- |
| EVAL-1 | Reading order: is the prose in the right order? (ING-3, ING-4, ING-5) | 20 fixture PDFs, `*.expected.jsonl` | Word-sequence edit-distance score (D14) plus char-mass guard; mean, min, per class | 0 |
| EVAL-2 | Sentence boundaries: are sentences split where a reader would pause? (ING-5, SYN-1) | 15 `*.sentences.txt` | Boundary precision, recall, F1 (D18); mean F1, min recall | 0 |
| EVAL-3 | Clean text: how much junk reaches the voice? (ING-1 to ING-6) | Same 15 fixtures | Quality checklist counts per 1 000 words, per check and total | 0 |
| EVAL-4 | Speech form: does the text sent to the voice read aloud correctly? (ING-6, ING-7, SYN-4) | `evals/data/speech_form.jsonl`, ~300 raw → spoken pairs (numbers, dates, units, ordinals, abbreviations, acronyms, table and equation cues) | Phoneme match through the backend's text front-end (`kokoro_backend.build_g2p`: misaki G2P, num2words shim, OOV fallback; no weights): actual and expected text both phonemized, phoneme-token edit distance as partial credit; word-level text match reported alongside (`text_exact`, `text_partial`); accuracy per category. For every `term_*` category the pair's score is the joined phoneme similarity (1 − character edit distance / expected length over the phoneme string with stress marks and spaces removed), with partial and exact kept in the record (built 2026-10-20, phase 4). A `term_*` row's expected text is a correct pronunciation respelled so the backend's front-end reads it as intended, and matches the backend where it already says the word correctly | 0 |
| EVAL-5 | Intelligibility: can the audio be understood? (SYN-1, SYN-4) | 50 fixture sentences | Round trip TTS → ASR (Whisper, MIT, dev-only) → word error rate vs the normalized input; mean, worst, per voice | 1 |
| EVAL-6 | Sync: do the word timestamps match the audio? (SYN-1, PLAY-3) | Same 50 sentences | ASR word timings vs backend timestamps: mean absolute offset (ms), p95, share within 150 ms, per speed 0.5/1/2/3x | 1 |
| EVAL-7 | Speed: how fast is synthesis on this machine? (SYN-5) | 20 bench sentences | `bench.py` time-to-first-audio p50/p95 and real-time factor | 1 |
| EVAL-8 | OCR: how accurate is the scanned path? (ING-2) | 5 scanned fixtures | Character error rate vs expected text; mean, max | 1 |
| EVAL-9 | Listening: does it sound good to a person? | 10 sentences × 2 voices | 1–5 rubric (naturalness, pronunciation errors counted, pacing) filled by a human; mean per voice, error count | 2 |
| EVAL-10 | Spoken mathematics: is an equation read as a person would read it aloud? (MATH-1 to MATH-4) | The M5 fixture `*.spoken.txt` files plus `evals/data/math_speech.jsonl`, raw → spoken pairs (added 2026-10-17) | D14-style word-sequence score over the spoken text (lowercased, punctuation stripped); per-class aggregates: display, inline, symbol table, references | 0 |
| EVAL-11 | Domain notation: is a unit, formula, amount, citation or statistic read as a teacher would read it aloud? (DOM-1 to DOM-26; DOM-27 is the suite itself) | `evals/data/domain_speech.jsonl`, raw → spoken pairs with `domain` and `class` across six domains (added 2026-10-19, D50; `docs/PRD_DOMAINS.md`) | The EVAL-10 scorer; aggregates per domain and per class, plus raw-symbol leaks | 0 |
| EVAL-12 | Web extraction: does the extension read a web page's article prose in reading order? (EXT-18, M10, proposed 2026-10-22) | 10 saved fixture pages under `api/tests/fixtures/web/` with golden `<stem>.expected.txt` (`docs/PRD_EXTENSION.md`) | D14 word-sequence score of the extracted prose, ≥ 0.95 per page (M10 gate (a)) | to decide in the M10 P1 spec (needs headless Chromium) |

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
| Audio format | PCM 24 kHz internally; Ogg Opus per segment by default, WAV optional (D16); browser matrix run in M3: both decode on Chromium, WebKit and Firefox under Playwright (`_agent/results/421`–`423`). Decided 2026-10-17: Ogg Opus default (user played document 16 with Opus clips in their own Safari, `audio/ogg`, cache purged; user report 2026-10-17). The `opus` extra must be installed for the default to take effect; without `opuscodec` the encoder falls back to WAV with a logged warning; `YOMIKOE_AUDIO_FORMAT=wav` selects WAV. | WAV needs no dependency and decodes everywhere via decodeAudioData; Ogg Opus at 48 kbps (`opuscodec`, Apache-2.0, `opus` extra) is 6–8x smaller (42 KB vs 276 KB for a 5.75 s sentence) |
| Storage | SQLite + local filesystem | Single-user v1; swap to Postgres + S3 when multi-user |
| Job queue | In-process asyncio task queue | No Redis until there is more than one worker |
| Frontend | React + TypeScript, Vite | Web Audio API scheduled buffers for gapless playback (decided 2026-10-15, see Technical Design D5), Media Session API |
| Packaging | Docker Compose | One command, one service (`api`) that serves the API and the built web app (D30, confirmed by the user 2026-10-17; `docs/DOCKER.md`); library on a named volume; the bind-mount failure seen first on Colima was the fork race fixed by the spawn start method (D9 amendment, `_agent/results/596`); a bind mount is a documented option. Domains: see "Domains" below (D52) |
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

### Domains (D52, 2026-10-21)

Four names, one brand domain. None is wired into the code yet: v1 runs locally via Docker Compose. Hosting and the landing page are M9 Hosting (decided 2026-10-21, then as the final milestone; M10 Browser extension was added after it on 2026-10-22).

| Domain | Points at | Repo folder | Status | Notes |
|---|---|---|---|---|
| yomikoe.app | Landing page (static site) | `site/` | Live 2026-10-22 over HTTPS (GitHub Pages, D54; result 1265); getyomikoe.com redirect pending | Primary brand domain; the one printed everywhere. `.app` forces HTTPS. |
| app.yomikoe.app | The reader (React app) | `web/` | Exists, runs locally only | Library, player, highlighting. Subdomain, free in DNS. |
| api.yomikoe.app | FastAPI service | `api/` | Exists, runs locally only | Ingestion, synthesis, audio cache. Subdomain, free in DNS. |
| getyomikoe.com | 301 redirect to yomikoe.app | none | DNS rule only | Defensive .com; never printed. Set the redirect at the registrar or Cloudflare. |

## Data model and API

Three tables carry the whole product: a document, its ordered segments, and the audio cache. Everything the reader shows or plays is addressed by `segment_id`.

**Tables**

| Table | Key columns | Notes |
| --- | --- | --- |
| documents | id, title, filename, page\_count, status (uploaded, parsing, ready, failed), created\_at, voice\_id, speed, position\_segment\_id, position\_offset\_ms, profile\_json (ING-11, M5) | One row per upload; voice and speed are the per-document settings |
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
| POST | /documents | Upload a PDF (M10 adds JSON, HTML and plain-text bodies with `source_url`, EXT-15, `docs/PRD_EXTENSION.md`); 202 {id, status=parsing} (row goes uploaded → parsing before the parse is queued); same bytes again (sha256) → 200 with the existing id and status; non-PDF → 415; over 100 MB → 413 |
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
| Privacy | Documents, page text and audio go only to the user's own API (the local machine in v1; the API base URL the user configured for the browser extension, M10); no third party; no telemetry |
| Portability | Docker Compose on macOS and Linux; Apple Silicon must work (no CUDA-only deps in v1) |
| Observability | Structured logs per request; timing for parse, synth and cache hit rate exposed at /metrics |
| Resilience | A failed segment synthesis skips with a log line and keeps playing; a failed parse marks the document failed with a reason the UI shows |
| Testability | Backends and ingestion mockable; a 20-PDF fixture set with expected segment order checked in |
| Accessibility | Keyboard-only operation; highlight contrast meets WCAG AA; respects prefers-reduced-motion |

## Milestones

```
M1 Ingest + skeleton  -->  M2 Synthesis + stream  -->  M3 Reader UI  -->  M4 Library + polish  -->
Gate: 20 fixture PDFs      Gate: first audio in 2 s    Gate: highlight     Gate: 300-page soak
parse in correct order     at 0.5x-3x on CPU           drift < 1 word/10m  passes; Docker up

-->  M5 Academic reading         -->  M6 Domain reading                 -->
     Gate: 10 formula pages,          Gate: EVAL-11 >= 0.95 per domain,
     spoken-maths score >= 0.90       90 probe strings >= 13/15 per domain

-->  M7 Classroom view (proposed)    -->  M8 Sources and formats (proposed)
     Gate: board highlight on the         Gate: EPUB/DOCX re-exports within
     word box for >= 95% of 200 words     0.02 of PDF EVAL-1; Apple Books EPUB opens

-->  M9 Hosting (decided 2026-10-21)
     Gate: yomikoe.app, app. and api. subdomains live over HTTPS,
     getyomikoe.com redirects; hosted first audio meets the M2 target

-->  M10 Browser extension (decided 2026-10-22)
     Gate: EVAL-12 >= 0.95 on 10 web pages; 3-sentence selection
     round-trips; side-panel e2e: first audio in M2 target, page highlight >= 95%
```

M1 gate: 20 fixture PDFs parse in correct prose reading order (D12): the golden comparison covers heading, body, list, caption and footnote segments. The score is word-level (D14): word-sequence edit distance over the ordered prose, ≥ 0.95 per PDF (scanned fixtures at a 0.85 floor, D35) and ≥ 0.97 mean; the sentence-level score is printed as a diagnostic only.

Each milestone is one or two coding-agent sessions and ends with its gate passing in a test, not by inspection. Nothing in a later milestone starts until the gate before it is green; the gates are the acceptance tests the coding session should write first.

**What each milestone covers**

1. M1 Ingest + skeleton: ING-1 to ING-5, the `documents`/`blocks`/`segments` tables, `POST /documents` and `GET /documents/{id}/segments`, a CLI that dumps a PDF's segments to stdout for eyeballing. Start by collecting the 20 fixture PDFs: five academic two-column papers, five single-column reports, five scanned pages, five with heavy tables and equations.
2. M2 Synthesis + stream: SYN-1 to SYN-5, the Kokoro backend, the audio cache table, `GET /audio/{segment_id}` with its lookahead queue. Benchmark script that reports real-time factor and time-to-first-audio. Also (added 2026-10-16, after D14): a sentence-boundary truth independent of the extractor (ordered prose text with reviewed sentence breaks) and a boundary precision/recall metric over the word stream, gated in M2 because synthesis is where boundaries become audible; the M1 golden measures order only.
3. M3 Reader UI: PLAY-1 to PLAY-5, the React app with Web Audio scheduled playback and word highlighting from timestamps. Voice and speed pickers. Clause-level chunking of the first sentence at speeds < 1.0 (D19) is deferred to M4 (user decision 2026-10-17). The browser decode matrix for WAV and Ogg Opus (D16).
   Status 2026-10-17 (branch `m3-reader`): PLAY-1 to PLAY-5 built in `web/`; the browser gate passes on Chromium (asserted) and on WebKit and Firefox (reported, D22), 9 of 9 tests each (`_agent/results/436_e2e_chromium_gate.txt`, `437_e2e_webkit.txt`, `438_e2e_firefox.txt`); the decode matrix passes WAV and Ogg Opus on all three Playwright engines; first audio was measured in the browser against Kokoro at 0.5x, 1.0x and 2.0x (`_agent/results/445_first_audio_kokoro.txt`). Decisions taken in M3 (Technical Design D20–D25): Node installed user-local from the official tarball (D20); the Vite dev server proxies the API, no CORS, and FastAPI serves `web/dist` in M4 (D21); the gate is asserted on Chromium only (D22); voice or speed changes made while paused apply at the next Play (D23); pause is `AudioContext.suspend()` (D24); sections are derived in the client from heading segments until the server writes the sections table (ING-8, M4) (D25). Confirmed by the user 2026-10-17: D20–D25 as recorded; D19 clause chunking deferred to M4 (first-audio baselines `_agent/results/445_first_audio_kokoro.txt`, `452_first_audio_after.txt`); D16 default was held at WAV until one play in the user's own Safari; closed 2026-10-17, Ogg Opus is now the default. Hands-on procedure: `docs/M3_TESTING.md`; code map: `docs/CODE_MAP_M3.md`.
4. M4 Library + polish: LIB-1 to LIB-4, PLAY-6 to PLAY-8, ING-6 and ING-7, OCR fallback (ING-2), Docker Compose, the 300-page soak test. Carried from M3: clause-level chunking of the first sentence at speeds below 1.0 (D19; baselines `_agent/results/445_first_audio_kokoro.txt` and `452_first_audio_after.txt`: 0.5x cold mean 1883 ms, 1.0x 1423 ms, warm under 30 ms; script `web/scripts/measure_first_audio.mjs`); the default audio format (D16) settled 2026-10-17: Ogg Opus.
   Status 2026-10-17 (branch `m4-library`): LIB-1 to LIB-4, PLAY-6 to PLAY-8, ING-2 (OCR fallback), ING-7, ING-8 and Docker Compose built. Gate clause 1, the API soak: a generated 300-page PDF (6030 segments) reached `ready` in 6.89 s with peak RSS 119 MB (process) and 80 MB (children) (`_agent/results/525_soak_api.txt`). Gate clause 2, the browser soak on Chromium: first segment visible at 619 ms, last attached at 677 ms, three highlight probes pass, reload restores with a delta of 0 sentences (`_agent/results/542_soak_browser.txt`); every phase 2 spec passes on Chromium, WebKit and Firefox, 20 each (`_agent/results/543_e2e_chromium_all.txt`, `544_e2e_webkit_all.txt`, `545_e2e_firefox_all.txt`). Gate clause 3, Docker: built and lint-checked, not run, because the dev machine has no container runtime; the user runs `docker compose up --build` (`docs/DOCKER.md`, `_agent/drafts/m4-4-docker.md`). As built: ING-7 reads a table as a cue "Table N, R rows." (R counts the spoken rows; rows with no letters are skipped; adjacent table blocks on one page count as one table) and an equation as "Equation." (inline fragments still join their sentence unchanged); the D14 guard now measures the excluded mass from `LogicalBlock.raw_text` (`_agent/drafts/m4-3-build-rules.md`). ING-4/ING-5 carried fixes: bare-number page-marker lines are dropped except 19xx/20xx years, a heading that is a bare number is dropped, a heading ending in a hyphen joins the next line without a space, U+FB00–U+FB06 ligatures decompose (`_agent/drafts/m4-3-build-rules.md`, `_agent/specs/m4-library-interfaces.md` §3). ING-2: Tesseract behind `OCRBackend`, real engine not run because tesseract is not installed (`_agent/results/547_ocr_wired.txt`). LIB deviations from the spec: `PATCH` also bounds per-document speed to 0.5–3.0; an unset position is `{segment_id: null, offset_ms: 0}`, never null; `yomikoe purge-audio` needs `--data-dir`; `DELETE` returns 409 only while a document is parsing (`_agent/drafts/m4-1-build-lib.md`). Decisions taken in M4 (Technical Design D26–D30, D27 unused), all proposed, confirmed by the user 2026-10-17: position saved through the same `PATCH` with keepalive on `pagehide`, no `sendBeacon` (D26); OCR via a Tesseract subprocess with a fake in tests and `documents.ocr_skipped_pages` when no engine is present (D28); no reader virtualisation, decided by the soak (D29); one `api` Compose service serving `web/dist` (D30). Updated: D22 (WebKit and Firefox now run every phase 2 spec; Chromium still asserts) and D25 (sections written at ingestion; documents ingested earlier keep the client derivation). Not verified: Media Session on a real lock screen (PLAY-7) and the `pagehide` keepalive save (`_agent/drafts/m4-2-build-ui.md`). Code map: `docs/CODE_MAP_M4.md`.
5. M5 Academic reading (added 2026-10-17, user decision: YomiKoe is a study narrator for students and academics). Scope: MATH-1 to MATH-5, TERM-1 to TERM-4, PLAY-10, PLAY-11, the pause part of SYN-8, ING-10 cue and type (line-by-line reading with TERM-5 after M5), and ING-11 document profile; MATH-6 and TERM-5 come after M5. What it changes: ING-7's one-word equation cue ("Equation.") becomes the fallback of MATH-1, used only when an expression cannot be structured; equations are otherwise spoken in full (Technical Design D36, D37). Gate:
   (a) a new fixture set of 10 formula-heavy pages (5 from the existing table/equation fixtures with a text layer, 5 new, at least 2 from textbooks and 1 scanned; 2 of the 5 new pages come from a technical book with code listings, and may count as textbook pages), each with a `<stem>.spoken.txt` holding the expected spoken text of every equation segment and every sentence with inline maths;
   (b) a spoken-mathematics score defined like D14 (word-sequence edit distance over the spoken text, lowercased, punctuation stripped) ≥ 0.90 per text-layer fixture, ≥ 0.50 for the scanned one (the first engine's measured OCR-path score on that page, 0.543, rounded down to the nearest 0.05, so the gate catches a collapse of the OCR path without demanding scanned-maths work; MATH-6 raises it), mean ≥ 0.92;
   (c) EVAL-4 extended with MATH and TERM categories and no new failures against the M4 baseline;
   (d) a tier-1 listening sheet (EVAL-9) on 10 formula sentences across 2 voices with pronunciation errors counted;
   (e) the 20 fixture PDFs plus the 10 formula pages are classified (ING-11), and the expected class in a `profile` field of each fixture's expected file is matched for at least 28 of 30.
6. M6 Domain reading (decided 2026-10-19; user decision: the narrator reads domain notation, units, formulas, amounts, citations and statistics, as a teacher of that field would). Specified in `docs/PRD_DOMAINS.md`, where the user accepted all 29 recommended decisions on 2026-10-19. Scope: DOM-1 to DOM-27 and EVAL-11 (Technical Design D45–D51, confirmed 2026-10-19), in the phase order of `docs/PRD_DOMAINS.md` "Milestones" (phase 0: EVAL-11, its dataset and the profile `fields`, gate tests first). Starts after the M5 gate passes (`CLAUDE.md` milestone rule) and in a fresh session. Gate (`docs/PRD_DOMAINS.md`, "Gate test"):
   (a) `api/tests/test_dom_gate.py::test_dom27_domain_speech_floor`: EVAL-11 over `evals/data/domain_speech.jsonl` scores ≥ 0.95 per landed domain and ≥ 0.90 per class with ≥ 3 pairs, with zero raw-symbol leaks;
   (b) `test_dom_probe_strings`: the 90 probe strings of results 850–875 reach ≥ 13 of 15 correct per domain.
7. M7 Classroom view (proposed 2026-10-17, after M5; renumbered from M6 2026-10-19, now after M6 Domain reading; user direction: the student sees exactly what the narrator is reading, as in a classroom). Scope: VIEW-1 to VIEW-4, NOTE-1 to NOTE-4 and the word-box storage change at ingestion (Technical Design D38, D39); VIEW-5 and NOTE-5 after M7. Gate:
   (a) on the 20 fixture PDFs, the board highlight for a sampled spoken word lands on that word's box for at least 95 % of 200 sampled words (the box comes from ingestion, the sampled position from the same timestamps the text view uses);
   (b) 10 minutes of playback keeps the board on the spoken segment's page with no page lag over one segment;
   (c) a Chromium-asserted e2e spec like M3's;
   (d) a highlight and a note made in the browser survive a reload and appear in the export (NOTE-4).
8. M8 Sources and formats (proposed 2026-10-17, renumbered from M6 the same day and from M7 on 2026-10-19, after M7 Classroom view; user direction: read the books and documents the user already has in Apple Books, Kindle, cloud drives and other apps). Scope: SRC-1 to SRC-3 and LIB changes for multi-format rows (file type shown in LIB-1); SRC-4 if cheap. DRM-protected titles are out of scope (see the DRM boundary under Sources). Gate: the 15 text fixtures re-exported as EPUB and DOCX parse to the same prose at an EVAL-1 score within 0.02 of the PDF score, and one DRM-free Apple Books EPUB opens from the library folder.

After v1: SYN-7 second backend, SYN-8 pitch (its pause part moved into M5, 2026-10-17), PLAY-9 export (ING-9 more formats is now M8, SRC-1).

9. M9 Hosting (decided 2026-10-21, then as the final milestone; M10 Browser extension was added after it on 2026-10-22; user decision: hosting is a milestone, not future scope). Scope: the four names in the "Domains" table (yomikoe.app landing page as a static site in `site/`, app.yomikoe.app serving `web/`, api.yomikoe.app serving `api/`, getyomikoe.com as a 301 redirect), TLS on every name, the Docker Compose image deployed to a host, backups of the library volume, and the landing page itself. Requirement IDs (`HOST-n`) and the hosting provider are to be specified when the milestone is planned.

   Phase 1 (landing page, started 2026-10-21): the landing page in `site/` is deployed to GitHub Pages by `.github/workflows/site.yml`; the registrar steps are in `docs/HOSTING.md`. The provider is a proposed decision (Technical Design D54), awaiting user confirmation. HOST-4 and later are to specify at phase 2 planning.

   | ID | Priority | Requirement |
   |---|---|---|
   | HOST-1 | P0 | yomikoe.app serves the landing page in `site/` as a static site with no build step |
   | HOST-2 | P0 | yomikoe.app resolves and serves over HTTPS with a valid certificate (provider: GitHub Pages, D54 proposed) |
   | HOST-3 | P1 | getyomikoe.com answers 301 to https://yomikoe.app and is never printed |

   Gate (proposed, to confirm at planning):
   (a) each of the four names resolves and serves over HTTPS, with getyomikoe.com answering 301 to yomikoe.app;
   (b) a fixture PDF uploaded through app.yomikoe.app plays with first audio within the M2 target measured from the browser;
   (c) the M4 300-page soak passes against the hosted API;
   (d) a library volume restored from backup serves the same documents.

10. M10 Browser extension (decided 2026-10-22; user decision: "we also need a milestone to create a chrome plugin to read the page or selected page aloud"). Specified in `docs/PRD_EXTENSION.md`; decisions D55–D59 in the Technical Design, proposed 2026-10-22, awaiting user confirmation. Placed after M9 because the extension needs an API reachable from the browser: the local Docker Compose API today, api.yomikoe.app after M9 phase 2; its order relative to M7 and M8 (both still proposed) is an open question. Scope: a Chrome Manifest V3 extension in `extension/` (TypeScript + Vite) that reads the current page's main content (toolbar action or shortcut, Mozilla Readability in the extension) or the selected text (context menu), plays it in the side panel with the shared player state machine and scheduler from `web/src/player/` (D5, D10), and highlights the spoken sentence in the page; on the API side, `POST /documents` accepts HTML and plain text (the HTML and text part of SRC-1), stores `source_url`, and gets a CORS allow-list for the extension. Phases P1 API HTML/text ingestion, CORS, fixtures and EVAL-12; P2 extension skeleton; P3 shared player and in-page highlight; P4 e2e gate and docs. Chrome Web Store publishing is a user action (EXT-14, P2), not a gate item.

   | ID | Priority | Requirement |
   |---|---|---|
   | EXT-1 | P0 | A Chrome MV3 extension in `extension/` that loads unpacked; toolbar action and keyboard shortcut read the active tab |
   | EXT-2 | P0 | Page extraction with `@mozilla/readability` (Apache-2.0) on a clone of the live document; article HTML, title and URL sent to the API; visible-text fallback |
   | EXT-3 | P0 | Context-menu "Read selection with YomiKoe" sends the selection as plain text; the document holds exactly the selected sentences |
   | EXT-4 | P0 | Playback in the side panel with the shared `web/src/player/` state machine and scheduler, per-segment `GET /audio/{segment_id}` into Web Audio (D5, D10); no audio in the service worker |
   | EXT-5 | P0 | Side-panel controls (play/pause, previous/next, speed, voice) and the sentence list with the current sentence highlighted |
   | EXT-6 | P0 | In-page highlight of the spoken sentence by DOM range mapping; unmapped segments highlight in the side panel only (D59) |
   | EXT-7 | P0 | In-page follow scroll that stops when the user scrolls away; respects `prefers-reduced-motion` |
   | EXT-8 | P0 | One setting, the API base URL, default `http://localhost:8765`; host permission for that origin only |
   | EXT-15 | P0 | `POST /documents` accepts JSON `{source_url, title, html}` or `{source_url, title, text}` and raw `text/html`/`text/plain` through the same block schema and sha256 dedup |
   | EXT-16 | P0 | `documents.source_url` and `documents.format` stored (migration 0007), returned, shown in LIB-1 |
   | EXT-17 | P0 | CORS allow-list `YOMIKOE_CORS_ORIGINS` for `chrome-extension://` origins, exposing `X-Timestamps` and `X-Duration-Ms` |
   | EXT-18 | P0 | EVAL-12 over 10 saved fixture pages under `api/tests/fixtures/web/` |

   Gate (`docs/PRD_EXTENSION.md`, "Milestones"):
   (a) EVAL-12: on the 10 fixture web pages (news article, blog post, Wikipedia article, documentation page, academic HTML paper, forum thread, two-column marketing page, page with code blocks, page with MathML or inline maths, page behind a cookie banner) the extracted reading-order prose scores ≥ 0.95 against `<stem>.expected.txt` by the D14 word-sequence score, extraction headless in Chromium;
   (b) a selection of 3 sentences on any fixture page round-trips to a document of exactly those sentences;
   (c) a Playwright Chromium e2e with the unpacked extension loaded (persistent context) plays a fixture page from the side panel with first audio within the M2 target and the in-page highlight on the spoken sentence for ≥ 95 % of 100 sampled sentences;
   (d) the tier-0 evals show no regression after the HTML ingestion path lands (compare cited).

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
| Spoken mathematics from PDF glyphs without LaTeX source (M5, added 2026-10-17) | High | Structure from glyph geometry first (D37); an image-to-LaTeX model behind a flag only if licence-clean; the MATH-1 fallback cue is never silent |
| Kokoro's G2P mispronounces symbol words and domain terms (M5, added 2026-10-17) | Medium | TERM-1 lexicon written into misaki's gold lexicon as `lexicon_overrides.py` already does; EVAL-4 phoneme match per domain category |

**Open questions**

- [ ] Product name decided: YomiKoe; register yomikoe.com before the first push - still working
- [ ] Should speed be global or per document by default? Current plan: per document, with a global default -- this can be a global setting and the user should be able to change it
- [x] Cache format decided 2026-10-15: Opus at 48 kbps - lets go with opus. Amended 2026-10-16 (D16): WAV by default in M2, Ogg Opus at 48 kbps optional in process through `opuscodec` (`YOMIKOE_AUDIO_FORMAT=opus`); no external encoder binary. Which one becomes the default is decided in M3 with the browser matrix. Matrix run 2026-10-17: both formats decode on Chromium, WebKit and Firefox under Playwright (`_agent/results/436`–`438`, `422`, `423`); default settled 2026-10-17: Ogg Opus after a clean play in the user's own Safari (D16)
- [ ] Is a 2 s time-to-first-audio target realistic on an M1 laptop with Kokoro-82M on PyTorch CPU (D15)? Benchmarked in M2 (the gate sentence passes at 0.5x to 3.0x, `_agent/results/311_model_tests.txt`; some 200-character sentences exceed 2 s at 0.5x, `_agent/results/314_bench.txt`, D19). Measured in the M3 browser on 2026-10-17: at 1.0x and 2.0x every cold sample was under 2 s, at 0.5x none was (3 samples each, `_agent/results/445_first_audio_kokoro.txt`); after the prefetch-order fix (67119ab) the 0.5x cold mean was 1883 ms, worst 2009 ms, on three new sentences (`_agent/results/452_first_audio_after.txt`). Decided 2026-10-17 by the user: clause chunking (D19) is deferred to M4 with these numbers as the baseline; `web/scripts/measure_first_audio.mjs` re-measures it
- [ ] Do we need Marker in v1, or does pdfplumber plus a column-detection heuristic clear the 95% gate?
- [ ] Phone browser: does iOS Safari allow background playback through Media Session? MSE is not used (D5): playback is Web Audio, which iOS pauses in a background tab. Not verified in M3 as of 2026-10-17; the muted `<audio>` workaround (Technical Design D5) is not built; Media Session is PLAY-7 (M4)
- [ ] ING-6 number forms by ear (M4 sampler `_agent/results/497_number_forms/index.md`): two findings so far. The dash-range rule rewrites a phone number, "555-0123" becomes "555 to 0123"; "40°C" passes through the normalizer unchanged, so the backend reads it as one unknown word
- [ ] D19 clause-level chunking of the first sentence at speeds below 1.0: still deferred after M4 (baselines `_agent/results/445_first_audio_kokoro.txt`, `452_first_audio_after.txt`)
- [x] D16: Decided 2026-10-17: Ogg Opus default (user played document 16 with Opus clips in their own Safari, `audio/ogg`, cache purged; user report 2026-10-17). The `opus` extra must be installed for the default to take effect; without `opuscodec` the encoder falls back to WAV with a logged warning; `YOMIKOE_AUDIO_FORMAT=wav` selects WAV.
- [ ] PLAY-7 Media Session on a real phone lock screen: built in M4, not verified on a device (`_agent/drafts/m4-2-build-ui.md`)
- [ ] `DELETE /documents/{id}` does not cancel synthesis lookahead already running for that document, so a job in flight could recreate a file under `audio/{id}/` after the delete; not tested (`_agent/drafts/m4-1-build-lib.md`)
- [ ] M4 gate clause 3 (Docker): `docker compose up --build`, then `GET /documents` returns 200 and the app loads at `/`, to be run by the user on a machine with a container runtime (`docs/DOCKER.md`)
- [ ] OCR of mathematics: Tesseract misreads inline and display maths on scanned_04/05; equation detection on OCR blocks or a maths-capable engine is MATH-6, after M5 (D35, `_agent/results/591_golden_scanned_after.txt`)
- [ ] M5: which maths-to-speech approach, and under what licence? Survey done 2026-10-17 (`_agent/research/m5-math-speech-options.md`, licence evidence `_agent/results/607_math_speech_licences.md`), recommendation confirmed by the user 2026-10-17 (D37): own rule engine over pdfplumber glyphs first; MathCAT (MIT) or Speech Rule Engine (Apache-2.0, needs Node) as an optional MathML layer later; for scanned pages only the Pix2Text MFR weights (MIT on Hugging Face) or UniMERNet (Apache-2.0 code, weights licence unverified) are candidates; excluded: Nougat weights (CC-BY-NC), pix2tex weights (reported CC BY-NC-SA, unverified) and the pix2text package (AGPL-3.0 via doclayout-yolo)
- [ ] M5: do equation crops (MATH-5) need word boxes stored? Block bboxes are stored in `blocks` rows (the bbox of the block's first source fragment, `docs/CODE_MAP_M1.md`); word boxes are not; added 2026-10-17
- [ ] M8 (was M7): iOS has no share target for web apps, so "open in YomiKoe" from another iOS app needs a native shell or the Files picker (SRC-3); see the phone-browser question above on iOS background playback; added 2026-10-17
- [ ] M8 (was M7): is the Apple Books folder path (`~/Library/Containers/com.apple.BKAgentService/Data/Documents/iBooks/Books`) stable across macOS versions? Unverified; added 2026-10-17
- [ ] M7 (was M6): does "teaches" include explaining beyond the text? That would need a language model, is a non-goal today ("Summaries, chat-with-PDF"), and changes the offline and licensing story; user to decide. Added 2026-10-17
- [ ] M7 (was M6): word boxes at ingestion need a schema migration (per-word boxes per segment, or per span); storage cost unverified. Added 2026-10-17
- [ ] M7 (was M6): page rendering for the board: pypdfium2 already renders pages at 300 dpi for OCR (ING-2) and can render the board; image cache size unverified. Added 2026-10-17
- [ ] M7 (was M6): should the board be rendered in the browser with pdf.js (Apache-2.0) instead, so the server ships only coordinates? Decide in the M7 spec (D38). Added 2026-10-17
- [ ] M7 (was M6): annotations are anchored to segment id plus offsets (D39), so a re-ingested document (new ids, D7) loses them unless they are re-anchored by text match; whether to re-anchor, and how, is open. Added 2026-10-17
- [ ] M10 ordering (added 2026-10-22): M10 Browser extension is placed after M9; M7 Classroom view and M8 Sources and formats are still proposed. Does M10 come before or after M7 and M8? M10 lands the HTML and plain-text part of SRC-1, which M8 would build on (`docs/PRD_EXTENSION.md`, open questions). User to decide
- [ ] Kindle (added 2026-10-19): Fire tablets as a browser target, `.azw3` personal documents and the DRM refusal are specified in `docs/PRD_KINDLE.md` (KDL-1 to KDL-9; Technical Design D41–D44, proposed, not confirmed). Deferred by the user 2026-10-19: future scope, not part of the current implementation
