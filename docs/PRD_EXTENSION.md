# PRD: YomiKoe browser extension (M10 "Browser extension")

As of 2026-10-22 · Sowmya · Status: **decided 2026-10-22, starts after M9**. User decision of 2026-10-22: "we also need a milestone to create a chrome plugin to read the page or selected page aloud." Nothing here is built yet. Companion to `docs/PRD.md` (Milestones item 10 carries the P0 rows and points here); the decisions it proposes are D55–D59 in `docs/TECHNICAL_DESIGN.md`, all "Proposed 2026-10-22, awaiting user confirmation".

Evidence for this document is under `_agent/results/`: the Readability licence `1275_readability_licence.txt`, what `POST /documents` accepts today `1276_api_post_documents_accepts.txt`, the CORS and port check `1277_cors_grep.txt`, the web player modules `1278_web_player_files.txt`. Facts about Chrome APIs that no run in this repo has checked are marked "unverified; from the worker's knowledge, Chrome 114+" and are repeated as open questions.

## Overview

A Chrome extension (Manifest V3) that reads the web page the user is on, or the text they selected, aloud with YomiKoe's voice, highlighting the spoken sentence in the page. It is a second client of the same API as the reader in `web/`: it never synthesizes speech itself and never names a TTS model (the `TTSBackend` rule in `CLAUDE.md`).

Two entry points:

1. **Read this page.** The toolbar button (or a keyboard shortcut) extracts the page's main content with Mozilla Readability, posts it to the API as a document, opens the side panel and plays it from the top.
2. **Read the selection.** A context-menu item on selected text posts exactly that text as a plain-text document and plays it.

Why it is a milestone and not a feature of M8: it is the first real consumer of SRC-1's HTML and plain-text path (so the API side of M10 lands part of SRC-1 early, see "Data model and API"), and it adds a new client with its own runtime (side panel, content script, service worker), its own permissions model and its own gate. Why after M9: the extension needs an API reachable from the browser, which is the local Docker Compose API today (host port 8765, `docs/DOCKER.md`, `_agent/results/1277_cors_grep.txt`) and api.yomikoe.app once M9 phase 2 hosts it.

## Goals, non-goals and success metrics

**Goals**

- On a typical article page, one click reads the article, not the navigation, ads, cookie banner or comments (EXT-2, gate (a)).
- A selection reads exactly what was selected, sentence for sentence (EXT-3, gate (b)).
- Playback has the same guarantees as the reader: per-segment fetch into Web Audio scheduled buffers (D5), the same player state machine (D10), first audio within the M2 target of 2 s (gate (c)).
- The spoken sentence is highlighted in the page itself, and in the side panel when the page cannot be mapped (EXT-7, D59).
- Page text goes only to the API the user configured (EXT-8, Privacy).

**Non-goals**

- **Firefox and Safari in M10.** Manifest V3 is supported by Firefox and Safari in some form, so a port is a later option, not designed against (unverified; from the worker's knowledge). Edge and other Chromium browsers may load the extension unchanged, untested.
- **Synthesis in the browser.** No WASM or on-device TTS; the extension only calls the API.
- **A full reader in the extension.** Library management (LIB-3 settings, LIB-4 delete), sections and the PDF reader stay in `web/`; the side panel links to the document in the web app.
- **Reading pages the user cannot see:** no crawling, no following links, no reading behind logins on the user's behalf. The extension reads the DOM the user already has open.
- **Publishing in the Chrome Web Store as a gate item.** Listing is a user action (EXT-14, P2).
- **Reading Chrome's built-in PDF viewer tabs** in M10 (open question below).
- **Telemetry** of any kind.

**Success metrics**

| Metric | Target | How measured |
| --- | --- | --- |
| Extraction quality on the 10 web fixtures | D14 word-sequence score ≥ 0.95 per page against `<stem>.expected.txt` | EVAL-12, gate (a) |
| Selection round-trip | 3 selected sentences become a document of exactly those 3 sentences | Gate (b) |
| First audio from the side panel | Within the M2 target (2 s on CPU at 1.0x, PRD "Latency") | Gate (c) e2e, the D19 `firstAudio` instrumentation of `machine.ts` |
| In-page highlight on the spoken sentence | ≥ 95 % of 100 sampled sentences | Gate (c) e2e |
| No regression in ingestion | Tier-0 evals: 0 unexplained regressions (D33) after the HTML path lands | Gate (d), `python -m yomikoe.evals compare` |

## Users and use cases

| Persona | Core need | What they do |
| --- | --- | --- |
| Student reading course pages and articles | Listen to a long article while following along | Click the toolbar button on the article, follow the highlight in the page |
| Academic reading an HTML paper (arXiv HTML, journal pages) | Hear the paper without downloading the PDF | Click the toolbar button; maths in MathML reads with the MATH-1 fallback cue until a MathML reader exists |
| Anyone skimming a forum or documentation page | Hear one part, not the whole page | Select the paragraphs, right-click, "Read selection with YomiKoe" |
| Self-hoster | Keep their reading private | Points the extension at their own API (default `http://localhost:8765`) |

**Core flows**

1. Open an article, click the YomiKoe toolbar button (or press the shortcut). The side panel opens with "Reading <title>", the sentence list appears as segments arrive, playback starts, the page scrolls to and highlights the spoken sentence.
2. Select three sentences, right-click, "Read selection with YomiKoe". The side panel opens and reads those three sentences only; the selection is highlighted sentence by sentence.
3. Click the toolbar button on the same article again tomorrow: the API returns the existing document (sha256 dedup) and playback resumes at the saved position (LIB-2).
4. The API is down or the base URL is wrong: the side panel says "Cannot reach YomiKoe at <url>" with a link to the settings; nothing is sent elsewhere.

## Functional requirements

Requirement family `EXT-n` (Extension), new on 2026-10-22; checked unused in `docs/`, `api/yomikoe/` and `web/src/` (`_agent/results/1276_api_post_documents_accepts.txt`, last block).

**Extension client (EXT)**

| ID | Pri | Requirement |
| --- | --- | --- |
| EXT-1 | P0 | A Chrome Manifest V3 extension in `extension/` (TypeScript + Vite, the toolchain of `web/`) that loads unpacked; a toolbar action and a keyboard shortcut (`commands`) start "read this page" on the active tab (D55) |
| EXT-2 | P0 | "Read this page" extracts the main content with `@mozilla/readability` run in the content script on a clone of the live document; it sends the article HTML, its title and the page URL to the API (D56). Pages Readability rejects (`isProbablyReaderable` false or `parse()` null) fall back to the body's visible text as plain text, with a notice in the side panel |
| EXT-3 | P0 | A context-menu item "Read selection with YomiKoe" on selected text sends `window.getSelection().toString()` as plain text with the page URL and title; the resulting document holds exactly the selected sentences (gate (b)) |
| EXT-4 | P0 | Playback runs in the side panel (`chrome.sidePanel`) with the shared player state machine and scheduler from `web/src/player/` (D10, D57), fetching `GET /audio/{segment_id}` per segment into Web Audio scheduled buffers (D5). The service worker holds no audio (D55) |
| EXT-5 | P0 | The side panel shows play/pause, previous/next sentence, speed and voice, the sentence list with the current sentence highlighted (PLAY-2 in the panel), and a link to open the document in the web app |
| EXT-6 | P0 | The spoken sentence is highlighted in the page (the PLAY-2 equivalent) by mapping each segment back to a DOM range and wrapping it; segments that do not map are highlighted in the side panel only, and the page highlight turns off for the document if fewer than half of the segments map (D59) |
| EXT-7 | P0 | The page scrolls to keep the highlighted sentence in view, and stops following when the user scrolls away, as PLAY-3 does in the reader; respects `prefers-reduced-motion` |
| EXT-8 | P0 | One setting, the API base URL (`chrome.storage.sync`), default `http://localhost:8765`; api.yomikoe.app is offered as a choice once hosted (M9 phase 2). The extension asks for host permission for that origin only, when the user sets it (D58) |
| EXT-9 | P1 | Clear errors: API unreachable, document failed to parse (`fail_reason`), and pages where content scripts cannot run (`chrome://` pages, the Chrome Web Store, other extensions' pages): the action shows "YomiKoe cannot read this page" instead of failing silently |
| EXT-10 | P1 | Keyboard control inside the side panel with the reader's key map (`web/src/player/keys.ts`, PLAY-4) |
| EXT-11 | P1 | Re-reading the same content resumes at the saved position through the same `PATCH /documents/{id}` as the reader (LIB-2, D26); the extension's documents appear in the web app's library (LIB-1) with their source URL |
| EXT-12 | P1 | Navigating away or closing the tab stops playback and removes the page highlight; the side panel keeps the document so the user can reopen it in the web app |
| EXT-13 | P2 | Media Session in the side panel (PLAY-7) so hardware media keys control playback |
| EXT-14 | P2 | Chrome Web Store listing: icons, description, privacy disclosure, screenshots; publishing is a user action, not a gate item |

**API (EXT)**

| ID | Pri | Requirement |
| --- | --- | --- |
| EXT-15 | P0 | `POST /documents` accepts, besides a PDF upload, a JSON body `{source_url, title, html}` or `{source_url, title, text}`, and raw `text/html` or `text/plain` bodies; both go through the same block schema as PDF (an HTML-to-block adapter for HTML, paragraph splitting for text), the same sha256 dedup (200 with the existing id for the same content) and the same 413 cap; anything else stays 415 (D56) |
| EXT-16 | P0 | `documents.source_url` is stored and returned by `GET /documents` and `GET /documents/{id}`, and the library row (LIB-1) shows the page's host and links to it; `documents.format` records `pdf`, `html` or `text` (the column D44 proposes for M8, landed once) |
| EXT-17 | P0 | CORS for the extension: `YOMIKOE_CORS_ORIGINS`, a comma-separated allow-list of `chrome-extension://<id>` origins, empty by default (so the web app keeps D21's CORS-free setup); `X-Timestamps` and `X-Duration-Ms` are exposed to the allowed origins because the player reads them from `GET /audio/{segment_id}` (D58; header names from `api/yomikoe/routes/audio.py`, `_agent/results/1276_api_post_documents_accepts.txt`) |
| EXT-18 | P0 | EVAL-12 web extraction suite over 10 saved fixture pages under `api/tests/fixtures/web/` with golden `<stem>.expected.txt` files, scored by the D14 word-sequence score (gate (a)) |

Not requirements, stated so they are not reopened: no synthesis in the browser, no third-party endpoints, no telemetry, no reading of pages the user has not opened.

## Architecture and stack

```
 Chrome tab                         Side panel (extension page)                    YomiKoe API (FastAPI)
 +---------------------------+      +----------------------------------+          +---------------------------+
 | content script            |      | React app (extension/src/panel)  |          | POST /documents           |
 |  Readability(clone(doc))  | msg  |  POST /documents {html|text,     | HTTP     |  json/html/text -> blocks |
 |  -> {title, html, url}    |----->|    title, source_url}            |--------->|  (HTML-to-block adapter)  |
 |  selection -> text        |      |  poll GET /documents/{id}        |          |  -> segments (stage 5 on) |
 |                           |      |  GET /documents/{id}/segments    |          |                           |
 |  segment -> DOM Range map | msg  |  machine.ts reducer (D10)        |          | GET /audio/{segment_id}   |
 |  wrap + scroll highlight  |<-----|  schedule.ts + AudioContext (D5) |<---------|  Ogg Opus + X-Timestamps  |
 +---------------------------+      +----------------------------------+          +---------------------------+
          ^       ^                              ^
          |       | chrome.scripting.executeScript (activeTab)
 +--------+-------+--------------------------------------+
 | service worker (background): action click, commands,  |
 | contextMenus; opens the side panel; holds no audio    |
 +-------------------------------------------------------+
```

- **Service worker** (`extension/src/background.ts`): registers the context menu and the command, injects the content script into the active tab with `activeTab` + `scripting` (no broad host permissions), opens the side panel. An MV3 service worker has no DOM and no `AudioContext`, and is shut down when idle, so it cannot host playback (unverified; from the worker's knowledge, Chrome 114+). D55.
- **Content script** (`extension/src/content/`): runs Readability on `document.cloneNode(true)` so the live page is not mutated by extraction; sends `{title, html, source_url}` or `{text, source_url, title}` to the side panel; later receives segment texts, maps them to DOM ranges over the live page (D59) and draws the highlight.
- **Side panel** (`extension/src/panel/`): the only document with audio. It posts the content, polls the document status, pages through segments, and plays them with the shared player (D57). `chrome.sidePanel` is available from Chrome 114, and `sidePanel.open()` from a user gesture from Chrome 116 (unverified; from the worker's knowledge, Chrome 114+). Fallback if the side panel proves unsuitable (for example audio stops when the panel closes and that is judged wrong): an offscreen document (`chrome.offscreen`, reason `AUDIO_PLAYBACK`) holds the `AudioContext` and the side panel only shows controls (D55; unverified, from the worker's knowledge).
- **Shared player source** (D57). What `web/src/player/` holds today (`_agent/results/1278_web_player_files.txt`): `machine.ts` (328 lines, the D10 reducer), `schedule.ts` (200, pure timing helpers), `skip.ts`, `blockSpeed.ts`, `keys.ts`, `pauses.ts` have no DOM or browser-global use (the one `AudioContext` hit in `schedule.ts` is a comment); `schedule.ts` and `skip.ts` import types from `web/src/api/types`. `mediaSession.ts` uses `navigator.mediaSession` and creates an `<audio>` element on `document.body` (feature-detected). `usePlayer.ts` (1085 lines) is the React hook that owns the `AudioContext`, the source-node schedule, prefetch, the rAF highlight loop, window scroll and key listeners and `getBoundingClientRect` follow logic, and imports `fetchAudio` from `web/src/api/client`. Recommendation: a **TypeScript path alias** (`@yomikoe/player` → `../web/src/player`, `@yomikoe/api-types` → `../web/src/api/types.ts`) in `extension/tsconfig.json` and `extension/vite.config.ts`, not a workspace package, for M10. Trade-off: the alias needs no restructuring of `web/` and keeps one source of truth, but couples the extension to `web/`'s internal layout, so a refactor in `web/` can break the extension; the extension's `tsc --noEmit` and build join the web checks to catch that. A workspace package (`packages/player/`) is cleaner but moves files the M3–M5 e2e specs and code maps cite. P3 splits `usePlayer.ts` into a DOM-free engine (context, schedule, fetch, prefetch, with an injected API base URL) and the reader-specific follow and key parts, so both clients share the engine; the reader's e2e suite must stay green across that split.
- **Licences.** `@mozilla/readability` 0.6.0 is Apache-2.0 (npm registry metadata, `_agent/results/1275_readability_licence.txt`). Every other extension dependency follows the `CLAUDE.md` licence rule; whether `api/scripts/check_licences.py` covers npm dependencies of `web/` and `extension/` is not checked here (open question).
- **No change** to synthesis, the `TTSBackend` interface, the audio cache key (D6) or the audio format (D7, D16).

## Data model and API

**What exists today.** `POST /documents` takes a multipart `UploadFile`, refuses with 415 "only PDF uploads are supported" when `%PDF-` is not in the first 1024 bytes, hashes the bytes with sha256 and returns 200 with the existing id when that hash exists, else stores `pdfs/{sha256}.pdf` and queues ingestion (`api/yomikoe/routes/documents.py` lines 160–172, `_agent/results/1276_api_post_documents_accepts.txt`). The FastAPI app adds no CORS middleware and nothing in `api/yomikoe` or `api/pyproject.toml` mentions CORS (`_agent/results/1277_cors_grep.txt`); D21 keeps the web app CORS-free through Vite's proxy and same-origin serving. The latest migration is `0006_pronunciations.py` (1276), so the next is 0007 (the `0006` that `docs/PRD_KINDLE.md` proposes for D44 is taken).

**Schema (migration 0007).**

| Column | Type | Values | Why |
| --- | --- | --- | --- |
| `documents.format` | TEXT NOT NULL DEFAULT 'pdf' | `pdf`, `html`, `text` (later `epub`, `docx`, `md`, `azw3` for M8 and D44) | The job layer dispatches on it; M8's "file type shown in LIB-1" reads it; added once for M10 and M8 |
| `documents.source_url` | TEXT NULL | The page URL the extension sent; NULL for uploads | Shown and linked in LIB-1 (EXT-16); lets the user find the page again |

The posted content is stored as `sources/{sha256}.html` or `sources/{sha256}.txt` beside `pdfs/` so ingestion can be re-run (as a PDF can) and `DELETE /documents/{id}` (LIB-4) removes it.

**API changes.**

| Method | Path | Change |
| --- | --- | --- |
| POST | /documents | Also accepts `application/json` `{source_url, title, html}` or `{source_url, title, text}`, and raw `text/html` and `text/plain` bodies (EXT-15). sha256 is taken over the UTF-8 bytes of the `html` or `text` field (not the URL, so the same article from two URLs is one document, and a changed article is a new one). 202/200/413 as today; other types 415 |
| GET | /documents, /documents/{id} | Rows carry `format` and `source_url` |
| any | all | CORS for `YOMIKOE_CORS_ORIGINS` only, exposing `X-Timestamps` and `X-Duration-Ms` (EXT-17) |

No other endpoint changes: segments, audio and positions are addressed by `segment_id` exactly as for a PDF.

**Which parts of SRC-1 M10 lands, and which stay in M8.**

| Part of SRC-1 | Where |
| --- | --- |
| HTML and plain text through the same block schema, posted as a body (the extension's path) | M10 |
| The HTML-to-block adapter for the elements Readability emits (`h1`–`h6`, `p`, `li`, `blockquote`, `pre`/`code`, `table`, `figcaption`, MathML) with the block types of `docs/PRD_KINDLE.md` KDL-5 | M10 (the adapter M8 extends) |
| `documents.format` column | M10 (migration 0007) |
| EPUB, DOCX and Markdown | M8 |
| Uploading `.html`, `.txt`, `.md` files through the web app's file picker and multi-file import (SRC-2) | M8 |
| The file type badge in LIB-1 for multi-format rows | M8 (M10 shows only the source URL) |

Known interface gap, quoted from `docs/PRD_KINDLE.md` "Architecture and stack" and not re-checked here: `ingest()` takes a PDF path, and `compute_profile` and `apply_mathspeak` take `pages: list[Page]`, which HTML does not have; the adapter enters at the stage 4 output (`list[LogicalBlock]`) and the P1 spec decides what `page` and `source` mean for HTML.

## Non-functional requirements

| Area | Requirement |
| --- | --- |
| Privacy | Page text, selections and audio go only to the API base URL the user configured (default their own machine); no third-party endpoint, no analytics, no telemetry, no remote code. The extension stores only the base URL and per-tab state. The Chrome Web Store disclosure (EXT-14) says the same |
| Permissions | `activeTab`, `scripting`, `contextMenus`, `sidePanel`, `storage`; host permission only for the configured API origin, requested at runtime; no `<all_urls>` content script |
| Licensing | Readability Apache-2.0 (1275); every npm and Python dependency under the `CLAUDE.md` rule, transitive imports included |
| Latency | First audio within the M2 target (2 s) measured from the click in the side panel; extraction itself is not budgeted separately until EVAL-12 measures it |
| Robustness | A page that Readability cannot parse falls back to visible text (EXT-2); a highlight that cannot be mapped falls back to the side panel (EXT-6); the page DOM is restored when playback stops |
| Accessibility | Side panel keyboard-operable (EXT-10); highlight contrast meets WCAG AA in the page and the panel, on light and dark pages; respects `prefers-reduced-motion` |
| Evals | EVAL-12 joins the eval layer (`api/yomikoe/evals/`, D31–D34); every change to `api/yomikoe/ingestion/` runs tier-0 evals before and after and cites the compare (`CLAUDE.md` evals rule); fixtures are pages the project saved, never user data |
| Offline | With a local API the extension needs no network beyond the page itself |

## Milestones

M10 starts after M9 (`docs/PRD.md`, Milestones item 10) in a fresh session (`CLAUDE.md` cost rule 8a). The gate tests are written first.

| Phase | Scope | Exit |
| --- | --- | --- |
| P1 API HTML and text ingestion | EXT-15 to EXT-18: JSON/HTML/text bodies on `POST /documents`, the HTML-to-block adapter, migration 0007 (`format`, `source_url`), CORS allow-list, the 10 fixture pages and goldens under `api/tests/fixtures/web/`, the EVAL-12 harness | Gate (a) and (d) tests written and run; tier-0 compare cited |
| P2 Extension skeleton | EXT-1 to EXT-3, EXT-8, EXT-9: MV3 manifest, service worker, side panel, settings page, Readability extraction, context menu, posting and status polling | Unpacked extension posts a fixture page and a selection; gate (b) passes |
| P3 Shared player and in-page highlight | EXT-4 to EXT-7, EXT-10 to EXT-12: path alias, `usePlayer.ts` engine split, side-panel controls, DOM range mapping and highlight with fallback | Reader e2e suite still green; side panel plays a fixture page |
| P4 Gate, docs | Gate (c) e2e; `docs/CODE_MAP_M10.md` (planned); the guide "YomiKoe M10 Extension Map", opened when the milestone starts, not now; EXT-13/EXT-14 if time allows | Gate (a)–(d) green |

**Gate (a)–(d).**

(a) EVAL-12: on 10 saved fixture web pages under `api/tests/fixtures/web/` (news article, blog post, Wikipedia article, documentation page, academic HTML paper, forum thread, two-column marketing page, page with code blocks, page with MathML or inline maths, page behind a cookie banner), the extracted reading-order prose scores ≥ 0.95 against a golden `<stem>.expected.txt` by the D14 word-sequence score; the saved pages and goldens are fixtures, and extraction runs headless in Chromium with the extension's own Readability bundle.

(b) A selection of 3 sentences on any fixture page round-trips to a document of exactly those 3 sentences (segment count 3, texts equal after whitespace normalization).

(c) A Playwright Chromium e2e with the unpacked extension loaded (persistent context) plays a fixture page from the side panel with first audio within the M2 target and the in-page highlight on the spoken sentence for ≥ 95 % of 100 sampled sentences.

(d) The tier-0 evals (`python -m yomikoe.evals run all --tier 0`) show no regression after the HTML ingestion path lands (compare output cited).

Suggested test names: `api/tests/test_ext_gate.py::test_ext18_web_extraction_floor` (a), `test_ext3_selection_roundtrip` (b); `extension/e2e/ext-gate.spec.ts` (c).

## Open questions and risks

| Risk | Likelihood | Mitigation |
| --- | --- | --- |
| Readability drops content on non-article pages (forum threads, docs with sidebars, marketing pages) | High | Gate (a) includes those classes; visible-text fallback (EXT-2); selection is always available |
| DOM mapping fails on pages that re-render (React/SPA hydration, infinite scroll) and the highlight drifts | Medium | Forward-only text matching with whitespace normalization; per-segment fallback to the side panel; gate (c) measures it |
| Wrapping text in the page breaks page scripts or layout | Medium | Wrap only the current sentence and unwrap on advance; restore the DOM on stop; CSS Custom Highlight API as an alternative (below) |
| Coupling through the path alias breaks the extension on a `web/` refactor | Medium | Extension typecheck and build in the suite (D57) |
| Side panel lifecycle stops audio when the user closes the panel | Medium | Accept (closing the panel is a stop), or the offscreen fallback (D55) |

**Open questions**

- [ ] Ordering: M10 is placed after M9 (decided 2026-10-22). M7 Classroom view and M8 Sources and formats are still "proposed"; does M10 come before or after them? M10 lands part of SRC-1 (HTML and text), which M8 would then build on. User to decide.
- [ ] Chrome versions (unverified; from the worker's knowledge, Chrome 114+): `chrome.sidePanel` from 114, `sidePanel.open()` on a user gesture from 116, no `AudioContext` in an MV3 service worker, `chrome.offscreen` with reason `AUDIO_PLAYBACK`. P2 confirms each on the installed Chrome and records the minimum version in the manifest.
- [ ] Does an extension page with host permission for the API origin need CORS at all, or does Chrome exempt it? (unverified; from the worker's knowledge, host permissions bypass CORS for extension pages in MV3.) EXT-17 specifies the allow-list regardless, because content-script fetches and a hosted API need it.
- [ ] Highlight mechanism: wrapping ranges (decided, D59) or the CSS Custom Highlight API (`CSS.highlights`), which paints ranges without mutating the page DOM (unverified; from the worker's knowledge, Chrome 105+)? Decide in the P3 spec.
- [ ] Firefox: MV3 with `sidebar_action` instead of `sidePanel`; a port after M10, not designed against now.
- [ ] Chrome Web Store publishing (EXT-14): who owns the developer account, and is a store listing wanted at all, or is "load unpacked" from a release zip enough?
- [ ] Pages that block content scripts (`chrome://`, the Web Store, PDF viewer, some enterprise policies): EXT-9 shows a message; is "read the selection via the clipboard" wanted there?
- [ ] PDF-in-browser tabs (Chrome's PDF viewer): non-goal for M10 as written. Option for later: the extension fetches the PDF bytes itself and posts them through the existing PDF upload, which needs no API change; the API fetching URLs itself is not proposed (it would make the API reach the network on a user's behalf).
- [ ] Very long pages: the 100 MB cap is far above any article; is a character cap with a "read the first N sections" prompt needed, and does first audio stay within target when ingestion of a long page is still running?
- [ ] Dynamic and infinite-scroll pages: the extension reads the DOM at the click; content loaded later is not read. Is a "continue with new content" action wanted?
- [ ] Hosted API (api.yomikoe.app): M9 does not specify accounts or auth; sending page text to a shared hosted API changes the privacy story. Until M9 phase 2 decides auth, is api.yomikoe.app offered at all?
- [ ] EVAL-12 tier: it needs headless Chromium, which tier 0 (about 15 s, Python only) does not run today; tier 0 with Chromium required, or tier 1? Proposed: extraction outputs are produced by the e2e harness and scored in Python, the rest decided in the P1 spec.
- [ ] Does `api/scripts/check_licences.py` cover npm dependencies of `web/` and `extension/`? Not checked in this document.
