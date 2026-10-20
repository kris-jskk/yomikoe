# PRD: HearNarro works with Kindle

As of 2026-10-19 · Sowmya · Status: proposed, not confirmed. Companion to `docs/PRD.md`; the decisions it proposes are D41–D44 in `docs/TECHNICAL_DESIGN.md`, all marked "proposed 2026-10-19, not confirmed".

Evidence for this document is under `_agent/results/`: parser licences `821_kindle_parser_licences.txt`, the subprocess precedent `822_d7_subprocess_precedent.txt`, the ingestion interface quoted from code `823_ingestion_interface.txt`, numbering `824_numbering.txt`. Device and Amazon-side facts that no run in this repo has checked are marked "supervisor brief, unverified".

## Overview

"HearNarro works with Kindle" means two things a Kindle owner asks for, and only two are buildable within the project's rules:

1. **Listen on a Kindle device.** Fire tablets run Fire OS (Android) with the Silk browser, which is Chromium-based, so the existing web app (per-segment HTTP fetch plus Web Audio scheduled buffers, D5) is expected to run there unchanged (supervisor brief, unverified on a device). E-ink Kindles cannot play HearNarro's audio at all (see Non-goals).
2. **Narrate what the user owns in their Kindle library.** The user's own documents (Send to Kindle, e-mailed, sideloaded) are downloadable unencrypted from amazon.com "Manage Your Content and Devices" > Content > Docs, as the original PDF or as `.azw3` (supervisor brief, unverified). A PDF already works today. An `.azw3` is KF8: a MOBI (PalmDB) container around EPUB-like HTML and CSS, so one HTML-to-block adapter can serve KF8 and EPUB (SRC-1) alike.

Purchased Kindle books are DRM-locked (`.kfx` on current apps) and stay out of scope, as the PRD's DRM boundary already says ("Sources (SRC)", `docs/PRD.md`). This PRD adds no exception to it.

Why a separate PRD: the main PRD carries Kindle only as SRC-4 (notes and highlights, P2, M7). The user asked how HearNarro relates to Kindle as a whole; the answer touches a device target (D41), an ingestion boundary (D42), a parser choice with a licence problem (D43) and a schema column (D44), which is more than one row.

## Goals, non-goals and success metrics

**Goals**

- A Fire tablet user opens HearNarro in Silk and gets the same playback, highlighting and resume as on a laptop browser (KDL-1).
- A user downloads a personal document from Amazon as `.azw3` and HearNarro narrates it through the same block schema as a PDF (KDL-3, KDL-5).
- A user who uploads a DRM-protected Kindle file gets a clear refusal that names why, never a broken parse (KDL-4).
- The library shows that a document came from Kindle (KDL-6).

**Non-goals**

- **E-ink Kindles (Paperwhite, Oasis, Scribe, basic) as a playback target** (D41). Their "experimental browser" is an old WebKit with no usable Web Audio, Bluetooth audio is routed only through Audible and VoiceView, the MP3 player was removed, and Audible on Kindle plays only Audible content (supervisor brief, unverified). There is no supported path to get HearNarro's audio out of the device. Jailbreak paths (KUAL, KOReader) are hobbyist, void the support story, and KOReader is AGPL-3.0, which the licence rule excludes (`CLAUDE.md`, Licensing).
- **DRM removal of any kind** (D42): no decryption, no key extraction, no reading of `.kfx` or encrypted `.azw`/`.azw3`. Legal and Amazon ToS exposure, and current `.kfx` tooling is unreliable (supervisor brief).
- **Reading Kindle app caches.** The local caches (Mac `~/Library/Containers/com.amazon.Lassen/Data/Library/eBooks/`, Windows `%USERPROFILE%\Documents\My Kindle Content\`, Android `/sdcard/Android/data/com.amazon.kindle/files/`) are listed for reference only; HearNarro never scans them, because they mix purchased (encrypted) and personal files and give no stable contract (supervisor brief).
- **Whispersync-style position sync** with Kindle devices or apps. Amazon has no public API for library contents or reading position, and scraping the Cloud Reader breaks the ToS (supervisor brief). HearNarro keeps its own position (LIB, D26).
- **Signing in to Amazon** from HearNarro. The user downloads files themselves; HearNarro never holds Amazon credentials (PRD Privacy row).
- A native Fire OS app. Same reasoning as the PRD's "Mobile native apps" non-goal.

**Success metrics**

| Metric | Target | How measured |
| --- | --- | --- |
| `.azw3` personal document vs the same document as PDF | EVAL-1 word score (D14) within 0.02 of the PDF's, and ≥ 0.95 | KDL gate test (below), EVAL-1 record |
| DRM-protected files refused | 100 % of the DRM fixture set returns the DRM refusal, 0 crashes | KDL-4 unit tests |
| Fire tablet playback | The M3 PLAY-1 to PLAY-5 hands-on checks (`docs/M3_TESTING.md`) pass on one Fire tablet in Silk | Manual, recorded under `_agent/results/` |
| Licence suite | `api/scripts/check_licences.py` stays green after the adapter lands | Test suite |

## Users and use cases

| Persona | Core need | What they do |
| --- | --- | --- |
| Student with a Fire tablet (primary for KDL-1) | Study on the cheap tablet they already carry | Open HearNarro in Silk on the home network, upload a PDF, listen with the highlight |
| Academic who sends papers to Kindle (primary for KDL-2) | Their reading pile already lives in "Send to Kindle" | Download the docs from Manage Your Content and Devices, drop them into HearNarro |
| Kindle highlighter (P2, = SRC-4) | Hear their highlights back | Copy `documents/My Clippings.txt` over USB or export from read.amazon.com/notebook, upload it |
| Owner of purchased Kindle books | Hear a bought book | Told plainly that DRM-protected books cannot be read (KDL-4); no workaround offered |

**Core flows**

1. On a Fire tablet, open the HearNarro URL in Silk, press play, lock the screen, keep listening (background playback is an open question, see below).
2. On amazon.com, Content > Docs, "Download & transfer via USB" a document; upload the `.azw3` or `.pdf` to HearNarro; tick "from Kindle" (or HearNarro infers it, D44); press play.
3. Upload a purchased book by mistake; see "This Kindle book is DRM-protected. HearNarro cannot read purchased Kindle books; personal documents you sent to Kindle can be downloaded unencrypted from Manage Your Content and Devices."

## Functional requirements

Requirement family `KDL-n` (Kindle), new on 2026-10-19; checked unused (`_agent/results/824_numbering.txt`). Highest ING id at writing is ING-11; no ING id is added.

**Device (KDL)**

| ID | Pri | Requirement |
| --- | --- | --- |
| KDL-1 | P1 | Fire tablets are a supported phone-class browser target (D41): the existing web app runs in Silk with no Fire-specific code path; PLAY-1 to PLAY-5 and the LIB resume flow pass the M3 hands-on checks on one Fire tablet. Any Silk-specific defect is fixed in the shared code, never by a user-agent branch |
| KDL-2 | P2 | Media Session (PLAY-7) and background playback verified on Fire OS; if Silk suspends Web Audio in a background tab, document it as for iOS (PRD open question on phone browsers), no native shell |

**Ingestion (KDL)**

| ID | Pri | Requirement |
| --- | --- | --- |
| KDL-3 | P1 | Ingest an unencrypted `.azw3` (KF8) personal document through the same block schema as PDF (extends ING-9 and SRC-1): detected by content (PalmDB type/creator `BOOKMOBI` at byte offset 60), not by extension; the KF8 section is located (the KF8 boundary record in a dual MOBI6+KF8 file, or the whole file if KF8-only), text records decompressed, the skeleton and fragment tables reassembled into XHTML parts in spine order, and each part fed to the shared HTML-to-block adapter (KDL-5). Parser per D43 |
| KDL-4 | P0 | DRM refusal (D42): a MOBI/KF8 file whose MOBI header encryption field is non-zero, any KFX or KFX-ZIP container (`.kfx`, `.kpf`, an `.azw` folder holding `.kfx` parts), and an `.azw`/`.azw3`/`.prc` that fails to decompress is refused with HTTP 415 and `detail: "drm_protected"`; the UI shows the message in Core flow 3. No decryption is attempted and no key is read. The refusal happens at upload, before a `documents` row is created |
| KDL-5 | P1 | Shared HTML-to-block adapter (extends ING-3, serves SRC-1 EPUB too): XHTML in document order becomes `LogicalBlock`s with the existing `BlockType`s: `h1`–`h6` → heading, `p` and `div` text → body, `li` → list, `table` → table (ING-7 cue), `figcaption` → caption, `pre`/`code` blocks → code (ING-10), `epub:type="footnote"`/`aside` notes → footnote, MathML → equation (MATH-1 fallback cue until a MathML reader exists, D37), images → never read; reading order is DOM order (no stage 3 layout pass); a navigation document (`nav`, NCX) builds the table of contents (ING-8) instead of being read |
| KDL-6 | P1 | A PDF downloaded from Manage Your Content and Devices needs no new code: it ingests through the existing PDF path. Whether a document came from Kindle is recorded per D44 and shown in the library row (LIB-1) |
| KDL-7 | P2 | Legacy MOBI6-only files (no KF8 section, older personal documents): read through the same PalmDB reader and the MOBI6 HTML, or refused with a clear "older Kindle format" message if MOBI6 markup proves too irregular; decided in the build spec |
| KDL-8 | P2 | Highlights and notes import: `My Clippings.txt` (USB) and the read.amazon.com/notebook export, plain text, one document per book title. This is SRC-4 restated, not new scope; the SRC-4 row in `docs/PRD.md` stays the canonical one |
| KDL-9 | P2 | A help page in the app: how to download personal documents from Manage Your Content and Devices, why purchased books cannot be read, and that HearNarro never asks for an Amazon login |

Not requirements, stated so they are not reopened: no DRM removal (D42), no Kindle cache scanning, no Amazon sign-in, no position sync, no e-ink target (D41).

## Architecture and stack

The ingestion entry point today is `ingest(pdf_path, *, document_id, ocr, on_page, ocr_backend) -> IngestResult` in `api/hearnarro/ingestion/pipeline.py`, which runs `extract_pages` → `apply_ocr` → `classify_pages` → `order_document` → `merge_blocks` → `compute_profile(pages, blocks)` → `split_sentences(block, ..., profile=)` → `apply_mathspeak(segments, blocks, pages, profile)` (quoted in `_agent/results/823_ingestion_interface.txt`). There is no format-adapter interface yet: the function takes a PDF path, and `POST /documents` refuses anything without `%PDF-` in the first 1024 bytes (`api/hearnarro/routes/documents.py`, quoted in 823). The seam an adapter can use is the stage 4 output: a `list[LogicalBlock]` (`api/hearnarro/ingestion/models.py`: `id`, `page`, `type: BlockType`, `text`, `source: list[tuple[int, int]]`, `raw_text`, `math_spans`). Stages 5 onward (segment, normalize, profile, mathspeak) work on `LogicalBlock`s.

Proposed shape (decided in the build spec, not here):

```
upload --sniff--> pdf   --> ingest() as today (stages 1-4 from glyphs)
                  azw3  --> kf8.read_book(path) -> list[XhtmlPart]  --+
                  epub  --> epub.read_book(path) -> list[XhtmlPart] --+--> html_blocks.to_blocks(parts) -> list[LogicalBlock]
                  drm   --> 415 drm_protected (KDL-4)                         |
                                                                              v
                                       compute_profile -> split_sentences -> apply_mathspeak -> IngestResult
```

- `api/hearnarro/ingestion/kf8.py` (new): PalmDB header and record table, MOBI and EXTH headers, encryption check (KDL-4), PalmDOC LZ77 decompression, KF8 boundary, FDST/SKEL/FRAG index reassembly into XHTML parts. Written from the public format description (MobileRead wiki "MOBI" and "KF8" pages), stdlib only (`struct`). Clean-room rule: nobody writing it reads KindleUnpack or `mobi` source, both GPL-3.0 (`_agent/results/821_kindle_parser_licences.txt`). HUFF/CDIC compression is a known gap: if a personal document from Amazon uses it, it is either implemented from the same public description or refused with a clear message (open question).
- `api/hearnarro/ingestion/html_blocks.py` (new, shared with SRC-1): XHTML to `LogicalBlock` (KDL-5) on the stdlib `html.parser`, so no new dependency; `lxml` (BSD-3-Clause) or `selectolax` (MIT) are permitted fallbacks if malformed markup demands it (821).
- Interface gaps the build spec must close, found in the code (823): `compute_profile` and `apply_mathspeak` take `pages: list[Page]`, which a reflowable book does not have (pass an empty list, or one synthetic `Page` per XHTML part, so `LogicalBlock.page` and the scanned share stay well defined); `LogicalBlock.source` is `(page, block.index)` into stage 1's blocks and needs a meaning for HTML (part index, element index); the job layer calls `ingest(pdf_path, ...)` and `pdf_page_count(pdf_path)` (`api/hearnarro/storage/jobs.py`, quoted in 823); the M6 board (D38) renders PDF pages, so an `.azw3` has no board view and the reader falls back to the text view.
- No change to synthesis, the `TTSBackend` interface, audio delivery (D5) or the player state machine (D10). The device side (KDL-1) changes no architecture.

Licence position (821, 822): every working KF8 reader found is copyleft (KindleUnpack GPL-3.0, its fork `mobi` 0.4.1 GPL-3.0-only, `libmobi` LGPL-3.0, `pymobi` GPLv3, `mobi_header` GPL-3.0); the one MIT-classified MOBI reader, `mobi-python` 0.0.1, has no LICENSE file and no evident KF8 support; for EPUB `ebooklib` is AGPL-3.0 and excluded, while `epubfile` (BSD-3-Clause) and `epub-utils` (Apache-2.0, alpha) are permitted. Calibre is GPL-3.0 and not on PyPI (the PyPI package named `calibre` is an unrelated MIT probability-calibration library).

## Data model and API

**Schema (D44).** The `documents` table has `filename` but no column for format or origin (DDL in `docs/TECHNICAL_DESIGN.md` "Storage (D7)"; migrations 0001–0005, checked in 823). `LogicalBlock.source` is a per-block provenance field, not a document source, and is not suitable. Proposed migration 0006 adds two columns:

| Column | Type | Values | Why |
| --- | --- | --- | --- |
| `documents.format` | TEXT NOT NULL DEFAULT 'pdf' | `pdf`, `azw3`, `epub` (later `docx`, `html`, `md`, `txt` for SRC-1) | Set from the content sniff at upload; the job layer dispatches on it; M7's "file type shown in LIB-1" reads it, so it is added once for both |
| `documents.origin` | TEXT NULL | `kindle`, later `apple_books`, `icloud`, ... (SRC-2, SRC-3); NULL = plain upload | A Kindle PDF is indistinguishable from any PDF by content, so origin is an upload field the user sets (or the client sets from an `.azw3` sniff); drives the "from Kindle" badge (KDL-6) |

**API.**

| Method | Path | Change |
| --- | --- | --- |
| POST | /documents | Accepts PDF and `.azw3` by content sniff; optional multipart field `origin`; DRM-protected Kindle files → 415 `{"detail": "drm_protected"}` (KDL-4); any other non-supported type → 415 as today |
| GET | /documents, /documents/{id} | Rows carry `format` and `origin` |

No other endpoint changes. Segments, audio and positions are addressed by `segment_id` exactly as for a PDF.

## Non-functional requirements

| Area | Requirement |
| --- | --- |
| Licensing | No copyleft code in the KF8 path, including transitive imports; the clean-room rule in Architecture applies; `api/scripts/check_licences.py` stays green. A Calibre subprocess is not adopted (D43) |
| Legal | No DRM circumvention; no Amazon login; no scraping of Amazon pages; no reading of Kindle app caches |
| Privacy | Kindle files stay on the machine like PDFs (PRD Privacy row); fixtures are documents the project owns, never user data (`CLAUDE.md` evals rule) |
| Throughput | A 300-page-equivalent `.azw3` parses in under the PDF target (60 s); no OCR path exists for it |
| Evals | Every change to `api/hearnarro/ingestion/` runs tier-0 evals before and after (`CLAUDE.md` evals rule); the `.azw3` fixture joins EVAL-1 as a new class `kindle` |
| Device | KDL-1 tested on one physical Fire tablet; no device-specific code |

## Milestones

Placement (proposed): **inside M7 "Sources and formats"**, as its second phase, after SRC-1's EPUB adapter. M7 in `docs/PRD.md` already names Kindle in its user direction and carries SRC-4; KDL-3 and KDL-5 reuse SRC-1's HTML-to-block adapter, so building them earlier would mean building that adapter early. KDL-1 (Fire tablet check) has no code dependency and can be run as a manual check at any milestone close from M5 on; it is cheap and answers the device question early. The existing M5–M7 text in `docs/PRD.md` is not changed by this document; adopting the placement is a supervisor or user decision.

| Item | Where | Depends on |
| --- | --- | --- |
| KDL-1, KDL-2 | Manual check at the next milestone close (M5 or M6) | A Fire tablet on the dev network |
| KDL-4, KDL-6, D44 migration | M7 phase 1, with SRC-1's upload sniff | M6 gate green |
| KDL-3, KDL-5, KDL-7 | M7 phase 2 | SRC-1 HTML adapter |
| KDL-8 (= SRC-4), KDL-9 | M7 if cheap, else after v1 | none |

**Gate test (specified, not written).** `api/tests/test_kdl_gate_azw3.py::test_kdl3_azw3_matches_pdf_golden`. Fixture: `api/tests/fixtures/kindle/<stem>.azw3`, a personal document the project owns, made by sending the existing fixture `api/tests/fixtures/pdfs/<stem>.pdf`'s source (or its EPUB re-export from M7's gate) through Send to Kindle and downloading it from Manage Your Content and Devices; at least two such fixtures, one single-column report and one with headings, lists and a table. Assertion: `ingest()` on the `.azw3` returns segments whose ordered prose (heading, body, list, caption, footnote, per D12) scores ≥ 0.95 on the D14 word-sequence edit distance against the PDF fixture's `<stem>.expected.jsonl`, and within 0.02 of the same document's PDF score; the block-type counts for heading and list match the PDF ingestion within ±1 per type; no segment comes from an image. A second test in the same file, `test_kdl4_drm_refused`, posts a synthetic PalmDB file with a non-zero encryption field and a minimal KFX-ZIP and asserts 415 `drm_protected` with no `documents` row created (the fixtures are synthetic headers, not real purchased books).

## Open questions and risks

| Risk | Likelihood | Mitigation |
| --- | --- | --- |
| Amazon serves personal documents as something other than PDF or unencrypted `.azw3` (e.g. KFX, or encrypted AZW) | Medium | KDL-4 refuses clearly; the gate fixture creation is the first step of M7 phase 2 and settles it (supervisor brief, unverified) |
| HUFF/CDIC-compressed text records in Amazon-converted files | Medium | Implement from the public description or refuse with a clear message; checked on the gate fixtures |
| Clean-room discipline slips and GPL code is copied into `kf8.py` | Low | Brief says so explicitly; the reviewer checks against the public spec; licence suite cannot detect copied code, so this is a review item |
| Silk suspends Web Audio in a background tab | Medium | Same mitigation as iOS (PRD open question); documented, no native shell |
| KF8 markup varies (Word-converted docs, inline styles, no semantic headings) | Medium | Heading detection falls back to font-size and bold style rules like stage 2; EVAL-1 `kindle` class tracks it |

**Open questions**

- [ ] D41: is a Fire tablet available for the KDL-1 check, and which Fire OS version? (supervisor brief, unverified on a device)
- [ ] D42: confirm that "Download & transfer via USB" on Manage Your Content and Devices returns unencrypted `.azw3` for converted personal documents and the original PDF for PDFs (supervisor brief, unverified)
- [ ] D43: accept the in-house reader with the clean-room rule, or allow an optional user-installed Calibre subprocess? The recorded subprocess precedent is not ffmpeg any more: D7's ffmpeg subprocess was replaced by in-process `opuscodec` (D16) and "There is no ffmpeg anywhere"; the live subprocess precedent is Tesseract (D28), which is Apache-2.0, not copyleft (`_agent/results/822_d7_subprocess_precedent.txt`). `CLAUDE.md` line 15 still says "Opus/WebM via an ffmpeg subprocess (D7)", which no longer matches the Technical Design (822)
- [ ] D44: should `origin` be inferred (an `.azw3` upload sets `kindle`) or only user-set? Proposed: inferred for `.azw3`, user-set for PDF
- [ ] KDL-7: are MOBI6-only personal documents common enough to support, or refused?
- [ ] Board view (M6, D38) for reflowable books: none in this PRD; a rendered-HTML board is a later question
