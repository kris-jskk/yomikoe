# HearNarro M1 code map: ingestion, storage, documents API and the gates

This document explains how the M1 code works end to end and what every M1 module and file
does. It is written for an engineer joining the project who has read `docs/PRD.md` (what) and
`docs/TECHNICAL_DESIGN.md` (how) once and now needs to find their way around the code. The
reasoning behind each stage, with diagrams, is in `docs/guide/m1-ingest-map.html`; this
document is the code-level companion to it and to `docs/CODE_MAP_M2.md`.

Unlike M2, M1 is finished: every module below exists and is covered by tests that passed in a
saved run. Where a rule here differs from the prose in the Technical Design, the code is what
is described and the difference is listed under "Open items".

## Scope and status

**As of commit `fa7b257`** on branch `m2-synthesis`. All code and tests were read from that
commit (`git show fa7b257:<path>` for the two files that are modified in the working tree).
The M1 tests were run on an export of that commit (`git archive fa7b257 api`), not on the
working tree, so the run is not disturbed by work in progress:
`_agent/results/296_m1_tests_at_head.txt`, **310 passed, 5 skipped, 1 failed** (the 5 skips are
the scanned fixtures without Tesseract; the failure is the environment licence scan, see
"Dependencies and licences"). The per-file inventory, with how each status was decided, is in
`_agent/results/294_m1_code_inventory.txt`.

Two files are being changed by another worker while this is written:

- `api/hearnarro/ingestion/segment.py` (the sentence splitter) is modified in the working tree
  (171 lines added, 13 removed against `fa7b257`). This document describes **the committed
  version** (pysbd only, 63 lines) and marks it "changing".
- `api/hearnarro/ingestion/abbreviations.py` is untracked (not in `fa7b257`). It is the
  abbreviation table for the new splitter. It is listed but not described.

**Update after the read.** While this document was being written, the branch moved from
`fa7b257` to `bc3657c`: commit `5e686db` ("ING-5: splitter keeps abbreviations, initials, section
numbers and closing quotes inside the sentence") committed the new `segment.py`,
`abbreviations.py` and `test_ing5_segment.py`, and `1ec7f64` asserted the D18 boundary gate.
Those three files are therefore described here as they were at `fa7b257`, not as they are at
the tip; every other M1 file is unchanged between the two commits (`git diff --stat fa7b257 bc3657c`).

### What M1 delivers

M1 turns a PDF into ordered sentence segments in SQLite and serves them over HTTP:

- **ING-1** upload a PDF (up to 100 MB) through `POST /documents`; the parse runs in a
  process pool; status and page progress are rows in `documents`.
- **ING-2** extract text with layout (pdfplumber glyphs grouped into lines and blocks by our
  own rules, D13); pages without a text layer go to OCR when Tesseract is installed.
- **ING-3** classify each block (body, heading, caption, footnote, header, footer, table,
  equation, list, image, noise, figure, toc); headers, footers, page numbers, noise, figure
  text and tables of contents are never read.
- **ING-4** reading order: one or two columns per page, inline maths reattached to its line,
  footnotes last.
- **ING-5** merge lines (de-hyphenation), join paragraphs across page and column breaks, then
  split into sentences with offsets back into the merged block text.
- **ING-6 (subset)** normalization for speech (`normalized_text` plus `char_map`): citations
  dropped, `et al.`, percent, URLs, bare domains and e-mail addresses spoken with "dot" / "slash" / "at"; all-caps tokens left as written (the M2 backend
  decides spoken vs spelled), and acronym definitions collected per document. Roman numerals
  I..XXXIX after a structural word (part, chapter, book, section, volume, vol., act, scene,
  appendix, war, phase, stage, step, level, tier) become cardinal words ("PART II" -> "Part two"),
  and in a heading segment (`normalize(text, heading=True)`) a numeral alone or leading "II. Title"
  does too, except a bare "I". A dash between two plain 1..4-digit integers ("1–10", "pp. 10-12", "3 - 5") is spoken as a range, "1 to 10" (" to " mapped onto the dash), unless it is part of an identifier, decimal, time or a longer dash-joined number (ISBN, date). An equals sign between terms is spoken "equals" ("≠" as "does not equal"), spaced on both sides or unspaced between a number or single letter on each side ("x=5"), leaving "==", "=>", "<=", ">=", "!=" and "key=value" untouched. A rating, an integer 0..100 over exactly 10 or 100 ("2/10", "95/100"), is spoken "2 out of 10" and an asterisk spaced between terms ("Wealth * (Return on Investment)") is spoken "times", leaving "9/11", "1/2", "10/12/2020", "24/7", "**", "word*" and "* " bullets untouched. `hearnarro renormalize --data-dir D (--document-id N | --all)`
  re-applies the rules to stored segments and drops the audio cache rows of those that changed.
- A document quality checklist (`hearnarro check`, 12 checks), a CLI, an HTTP smoke script.
- ING-7 (table rows as prose) and ING-8 are not M1 (PRD milestones); OCR quality is M4.

### The gate

PRD M1: reading order correct on ≥ 95 % of the 20 fixture PDFs' segments. In test form
(`api/tests/test_ing4_reading_order_golden.py`, D11, D12, D14): word-level score ≥ 0.95 on each
fixture and ≥ 0.97 mean, plus an excluded-character-mass guard of 0.05. Last saved runs:

- `_agent/results/151_golden_d14.txt`: 15 text fixtures scored, all ≥ 0.95; **mean 0.9914,
  min 0.9710** (`tables_03_copula_subspaces`); sentence-level mean (diagnostic) 0.9203;
  `17 passed, 5 skipped`.
- `_agent/results/296_m1_tests_at_head.txt`: the same test module passes at `fa7b257`.
- `_agent/results/248_smoke_with_checks.txt`: the HTTP smoke over a running server, 15/15
  passed, mean 0.9914, 60 pages in 3.5 s (17.1 pages/s), `RESULT: PASS`.

The 5 scanned fixtures are skipped while `ocr_available()` is False (no `tesseract` binary);
their expected files are provisional until the OCR fallback lands (M4).

### Status words

| Word | Meaning |
| --- | --- |
| tested | Real code plus tests that passed in `_agent/results/296_m1_tests_at_head.txt`. |
| implemented | Real code; no dedicated test, or exercised only indirectly. |
| changing | Tested at `fa7b257`, but modified in the working tree by another worker right now. |
| red (env) | The test fails in the current virtualenv for a reason outside the code under test. |

### Status at a glance

| Piece | Status |
| --- | --- |
| Data model (`models.py`) | tested |
| Stage 1 extract (`extract.py`) | tested |
| Stage 2 classify (`classify.py`) | tested |
| Stage 3 order (`order.py`) | tested |
| Stage 4 merge (`merge.py`) | tested |
| Stage 5 segment (`segment.py`) | changing (tested at `fa7b257`) |
| Abbreviation table (`abbreviations.py`) | changing (untracked; not in `fa7b257`) |
| Normalization (`normalize.py`) | tested |
| Pipeline (`pipeline.py`) | tested |
| Quality checklist (`quality.py`) | tested |
| CLI (`cli.py`, `__main__.py`) | implemented (`check` exercised through `check_pdf` in tests) |
| App factory (`app.py`, M1 part) | tested through `test_api_documents.py` |
| Documents API (`routes/documents.py`) | tested |
| Storage (`storage/db.py`, `repo.py`, `jobs.py`, migrations 0001/0002/0003; 0003 adds `documents.acronyms_json`) | tested; migrations also run by hand (result 225) |
| `scripts/m1_smoke.py` | implemented; run against a server (results 170, 248) |
| `scripts/check_licences.py` | tested (`test_classify`, `test_allowlist_covers_no_metadata`); environment scan red (env) |
| Reading-order gate | passing (151, 296) |

## Code flows

Each flow is a numbered list of steps. Each step names **file → function** and what crosses
the boundary (types, HTTP fields, rows, files). All paths are under `api/`.

### a. `POST /documents` upload to `ready`

```
client          FastAPI handler (event loop)        SQLite              process pool worker
  |  POST /documents (multipart)  |                      |                        |
  |------------------------------>| _read_capped (413)    |                        |
  |                               | %PDF- check (415)     |                        |
  |                               | sha256                |                        |
  |                               |-- get_document_by_sha256 ->| (hit: 200 {id,status})
  |                               | write pdfs/{sha}.pdf (thread)                   |
  |                               |-- insert_document 'uploaded' ->|                 |
  |                               |-- set_status 'parsing' ------->|                 |
  |                               |-- run_in_executor(run_ingestion) ------------->|
  |<----- 202 {id, "parsing"} ----|  task: _watch_ingestion(future)                 |
  |                               |                      |<- page_count, pages_done=0
  |                               |                      |<- pages_done every 10 + last
  |                               |                      |   ingest(pdf) ... (flow c)
  |                               |                      |<- one txn: DELETE old rows,
  |                               |                      |   INSERT blocks, segments,
  |                               |                      |   UPDATE status='ready', title,
  |                               |                      |   page_count, pages_done, parse_ms
  |                               |<--------------- future result (wall seconds) ---|
  |  GET /documents/{id} (poll)   |                      |                        |
  |------------------------------>|-- get_document ----->|                        |
  |<-- {status: ready, pages_done, parse_ms, title, ...}  |                        |
```

1. **HTTP in.** uvicorn → FastAPI → `hearnarro/routes/documents.py` →
   `async def upload_document(request: Request, file: UploadFile, conn: Conn) -> Any`. `Conn`
   is `Annotated[aiosqlite.Connection, Depends(get_conn)]`; `get_conn` opens one connection per
   request from `request.app.state.engine.connect()` (`storage/db.py` `Engine.connect`).
2. **Read with a cap.** `documents.py` → `async def _read_capped(file: UploadFile, max_bytes: int) -> bytes`
   reads 1 MiB chunks (`CHUNK`) and raises 413 as soon as the running total exceeds
   `app.state.max_upload_bytes` (`MAX_UPLOAD_BYTES = 100 * 1024 * 1024` in `app.py`, ING-1).
   The cap is enforced while reading, so a 2 GB upload is not buffered whole first.
3. **Is it a PDF.** `PDF_MAGIC = b"%PDF-"` must occur in the first 1024 bytes, else 415. Not
   `startswith`: some PDFs carry a few bytes of junk before the header and readers accept them.
4. **Deduplicate.** `hashlib.sha256(data).hexdigest()` →
   `storage/repo.py` `async def get_document_by_sha256(conn, sha256: str) -> dict[str, Any] | None`.
   A hit returns **200** `{"id", "status"}` of the existing row (whatever its status). The
   `documents.sha256` column is `UNIQUE` (migration 0001).
5. **Store the file.** `pdf_dir(data_dir) / f"{sha256}.pdf"` written with
   `asyncio.to_thread(pdf_path.write_bytes, data)` (`storage/db.py` `pdf_dir`). The file is
   named by content, so a second upload of the same bytes cannot overwrite a different PDF.
6. **Insert the row.** `repo.insert_document(conn, *, title: str, filename: str, sha256: str, status: str) -> int`
   with `status="uploaded"`, `title=Path(filename).stem` (a placeholder; the worker writes the
   real title). A concurrent upload of the same bytes that won the insert raises
   `repo.DuplicateDocument` (`sqlite3.IntegrityError`); the handler then answers 200 with the
   winner's id.
7. **Mark parsing before submitting.** `repo.set_status(conn, doc_id, "parsing")`. The order
   matters (module docstring): status is set to `parsing` before the job exists, so the
   worker's later `ready`/`failed` can never be overwritten by the handler.
8. **Submit to the pool.** `loop.run_in_executor(app.state.ingest_executor, run_ingestion, str(db_path(data_dir)), doc_id, str(pdf_path))`.
   Crosses into the worker: three picklable values (a path string, an int, a path string).
   The executor is `ProcessPoolExecutor(max_workers=INGEST_WORKERS)` with `INGEST_WORKERS = 2`
   (`app.py`, D9). Pinned by `test_ing1_ingestion_uses_process_pool_of_two`.
9. **Watch the job.** `asyncio.create_task(_watch_ingestion(request, doc_id, future))`, kept
   in `app.state.ingest_tasks` until done. `_watch_ingestion` stores the returned wall seconds
   in `app.state.ingest_seconds[doc_id]`; if the future itself raises (the worker process died,
   e.g. `BrokenProcessPool`) it writes `failed` with `"{type}: {message}"` from the event loop.
10. **Respond.** **202** `{"id": doc_id, "status": "parsing"}` without waiting for the parse.
11. **Worker: page count.** In the child process, `storage/jobs.py` →
    `def run_ingestion(db_file: str, document_id: int, pdf_path: str) -> float` →
    `_update(... "UPDATE documents SET page_count = ?, pages_done = 0, parse_ms = NULL ...")`
    with `pdf_page_count(pdf_path)` (pypdfium2). Every write in the worker uses its own
    blocking `sqlite3` connection from `connect_sync` (same pragmas as the API: WAL, foreign
    keys, `busy_timeout=10000`).
12. **Worker: progress.** `PageProgress(write, every=PROGRESS_EVERY)` with
    `PROGRESS_EVERY = 10` is passed as `on_page` to `ingest`; `extract_pages` calls
    `on_page(number + 1, total)` after each page, and `PageProgress.__call__` writes
    `pages_done` when `done % 10 == 0 or done == total`. Pinned by
    `test_ing1_page_progress_writes_every_10_pages_and_last` and
    `test_ing1_parse_progress_pages_done_reaches_page_count_documents_table`.
13. **Worker: parse.** `ingest(pdf_path, document_id=document_id, on_page=progress)` (flow c)
    returns an `IngestResult(pages, blocks, segments)`.
14. **Worker: title.** `pdf_title(pdf_path)` reads the Info `Title` (pypdfium2);
    `choose_title(meta_title, first_heading, filename)` keeps it unless it is missing, blank or
    filename-like (`FILENAME_TITLE_RE` `\.(?:indd|docx?|pdf|tex|pages|qxd)$` or no whitespace),
    else the first heading if it has 2 to 12 words (`TITLE_HEADING_WORDS = (2, 12)`), else the
    filename stem with `-`/`_` as spaces. Pinned by `test_ing1_choose_title` and
    `test_ing1_filename_like_metadata_title_falls_back_to_first_heading`.
15. **Worker: one transaction.** `_write_result(conn, document_id, result, title, parse_ms)`
    in `with conn:` (commit or roll back as a unit): delete the document's old `segments` and
    `blocks`; insert one `blocks` row per `LogicalBlock` (`"order"` = `LogicalBlock.id`,
    `merged_text` = `LogicalBlock.text`, bbox of the **first source raw block**, NULLs if not
    found); insert every segment with `block_id` remapped to the new `blocks.id`,
    `section_id NULL` and `char_map` packed by `pack_char_map` (uint16 little-endian); update
    the document to `ready`, `fail_reason NULL`, `page_count`, `pages_done = page_count`,
    `parse_ms`, `title`. A reader therefore never sees half a document's segments.
16. **Worker: failure.** Any exception inside `run_ingestion` → `mark_failed(db_file, document_id, f"{type(exc).__name__}: {exc}", parse_ms)`.
    Both outcomes set `parse_ms` (`_elapsed_ms`, at least 1). Pinned by
    `test_ing1_ingest_raises_sets_failed_documents_table`,
    `test_ing1_corrupt_pdf_fails_in_process_pool`,
    `test_ing1_failed_document_carries_parse_ms_documents_table`.
17. **Polling.** `GET /documents/{id}` → `get_document` returns the summary
    (`id, title, filename, sha256, page_count, pages_done, parse_ms, status, fail_reason,
    created_at, last_opened_at`) plus `sections` (empty in M1), `settings {voice_id, speed}`,
    `position {segment_id, offset_ms}`. 404 for an unknown id
    (`test_ing1_missing_document_returns_404`).

### b. `GET /documents/{id}/segments?from=&limit=` paging

1. `routes/documents.py` → `async def get_segments(document_id: int, conn: Conn, from_: Annotated[int, Query(alias="from", ge=0)] = 0, limit: Annotated[int, Query(ge=1)] = SEGMENTS_DEFAULT_LIMIT) -> dict[str, Any]`.
   `from < 0` or `limit < 1` is a 422 from FastAPI.
2. 404 if `repo.get_document` returns None.
3. `limit = min(limit, SEGMENTS_MAX_LIMIT)`: `SEGMENTS_DEFAULT_LIMIT = 100`,
   `SEGMENTS_MAX_LIMIT = 500`; larger limits are clamped, not rejected.
4. `repo.count_segments(conn, document_id) -> int` (`total`).
5. `repo.list_segments(conn, document_id, from_order, limit) -> list[dict[str, Any]]`: a
   range scan on the unique index `segments_doc_order (document_id, "order")` joined to
   `blocks` for the block `type`. Columns: `id, order, block_id, type, section_id, text,
   normalized_text, char_start, char_end`. `char_map` is not sent (it is for M2's offset
   translation, not for the reader).
6. Response: `{document_id, total, from, limit, next_from, segments}` where `next_from` is
   `rows[-1]["order"] + 1` if that is below `total`, else `null`. A client pages by following
   `next_from` until null (`scripts/m1_smoke.py` `all_segments`). Orders are dense (0..N−1),
   so `next_from` is also the count read so far. Pinned by `test_ing1_segments_paging_segments_table`
   and `test_ing1_report01_segments_match_ingest_blocks_segments_tables` (the API returns the
   same texts in the same order as calling `ingest` directly).

### c. `ingest(pdf)` stage by stage

```
pipeline.ingest(pdf_path, *, document_id=0, ocr=True, on_page=None) -> IngestResult
  |
  | extract.extract_pages(pdf_path, ocr=, on_page=)            stage 1  (ING-2, D13)
  |   pdfplumber page.chars -> list[LayoutChar] -> group_lines -> group_blocks
  |   -> page_from_layout -> Page(blocks: list[Block(lines: list[Line(spans: list[Span])])],
  |                               image_bboxes, table_bboxes, figure_bboxes, has_text_layer)
  v
  list[Page]                       every Block.type == "body"
  |
  | classify.classify_pages(pages)                             stage 2  (ING-3, D3, D12)
  |   sets Block.type in place; may set Block.lead, rewrite a block's lines (vertical title,
  |   drop cap)
  v
  list[Page]                       typed blocks
  |
  | order.order_document(pages) = concat(order_page(page))     stage 3  (ING-4, D2)
  |   drops unread types, columns, attach_inline sets Block.inline, footnotes last
  v
  list[Block]                      flat, reading order across the document
  |
  | merge.merge_blocks(blocks)                                 stage 4  (ING-5)
  |   lines -> text, inline fragments joined, cross-break joins, noise lines dropped
  v
  list[LogicalBlock(id, page, type, text, source)]
  |
  | for block: segment.split_sentences(block, document_id=, order_start=, id_start=)
  |   pysbd spans -> (char_start, char_end) into block.text -> normalize.normalize(sent)
  v                                                            stage 5  (ING-5, ING-6, D4)
  list[Segment(id, document_id, block_id, order, section_id=None, text,
               normalized_text, char_start, char_end, char_map)]
```

1. **Stage 1, extract.** `hearnarro/ingestion/extract.py` →
   `def extract_pages(pdf_path: str | Path, *, ocr: bool = True, min_text_chars: int = 20, on_page: Callable[[int, int], None] | None = None) -> list[Page]`.
   Per page: `_ligature_fixes` (per-font repair table, cached across pages) →
   `_layout_chars` (`LayoutChar` per glyph, top-left coordinates, descent fix, CID fix,
   ligature fix) → `group_lines` (`list[list[LayoutChar]]` with virtual spaces) →
   `rule_tables` + `has_columns` (booktabs tables) → `group_blocks` (`list[list[list[LayoutChar]]]`)
   → `page_from_layout` (`Page` of `Block`/`Line`/`Span`) → `figure_regions`. A page with
   fewer than 20 stripped characters gets `has_text_layer = False`, its blocks are cleared,
   and `ocr_page` replaces them when `ocr and ocr_available()`. Crosses out: `list[Page]`; every
   `Block.type` is the default `"body"`.
2. **Stage 2, classify.** `classify.py` → `def classify_pages(pages: list[Page]) -> list[Page]`.
   Document-wide `body_median_size(pages)` and `repeated_band_texts(pages)` first; then per
   page `_cover_tables`, `_classify` per block, the figure override, and the per-page passes;
   then the document passes `_mark_toc` and the off-page re-check. Mutates in place and
   returns the same list. Crosses out: `list[Page]` with `Block.type` set and possibly
   `Block.lead = True`.
3. **Stage 3, order.** `order.py` → `def order_document(pages: list[Page]) -> list[Block]`
   = `[b for page in pages for b in order_page(page)]`;
   `def order_page(page: Page, *, gap_frac: float = GUTTER_FRAC, full_width_frac: float = 0.60) -> list[Block]`
   returns leads + `attach_inline(_linearize(readable, ...))` + `_linearize(footnotes, ...)`.
   Crosses out: one flat `list[Block]` with unread types removed and `Block.inline` set on
   fragments.
4. **Stage 4, merge.** `merge.py` → `def merge_blocks(blocks: list[Block]) -> list[LogicalBlock]`.
   Crosses out: `list[LogicalBlock]` with ids 0..N−1 in reading order; `source` lists every
   `(page, block.index)` merged in.
5. **Stage 5, segment.** `segment.py` →
   `def split_sentences(block: LogicalBlock, *, document_id: int, order_start: int, id_start: int) -> list[Segment]`,
   called once per block by `ingest` with `order_start = id_start = len(segments)` so far.
   Each sentence is normalized by `normalize.py` →
   `def normalize(text: str) -> tuple[str, list[int]]`. Crosses out: `list[Segment]`; `order`
   is dense over the document; `id` equals `order` inside `ingest` (the database assigns its
   own `segments.id` on insert, flow a step 15).
6. **Result.** `IngestResult(pages: list[Page], blocks: list[LogicalBlock], segments: list[Segment])`.
   `pages` is kept because the worker needs raw block bboxes for the `blocks` rows and
   `check_pdf` needs per-page character counts.

### d. `hearnarro dump` and `hearnarro check`

Entry points: `hearnarro` console script (`pyproject.toml` `[project.scripts]` →
`hearnarro.cli:main`) or `python -m hearnarro` (`hearnarro/__main__.py` calls
`sys.exit(main())`). `def main(argv: Sequence[str] | None = None) -> int` builds an argparse
parser with three subcommands.

- **dump** `hearnarro dump <pdf> [--jsonl] [--no-ocr]` →
  `_dump(pdf: str, *, jsonl: bool, ocr: bool) -> int` → `ingest(pdf, ocr=ocr)` → one line per
  segment: `order<TAB>type<TAB>text`, or with `--jsonl` `{"order", "page", "type", "text"}`
  (the `.expected.jsonl` format, so a dump can be diffed against a fixture). `type` and `page`
  come from the segment's `LogicalBlock`. Exit 0. No database, no server.
- **check** `hearnarro check <pdf> [--json] [--no-ocr]` →
  `_check(pdf: str, *, as_json: bool, ocr: bool) -> int` → `quality.check_pdf(pdf, ocr=ocr)`
  (ingest, map segments to `QSeg(text, type)`, title via `choose_title`, `max_page_chars` over
  text-layer pages) → `QualityReport.table()` or `json.dumps(report.to_dict())`. **Exit 1 when
  any thresholded check fails**, so it can gate a script.
- **serve** `hearnarro serve [--data-dir DIR] [--host H] [--port N]` →
  `uvicorn.run(create_app(Path(data_dir) if data_dir else None), host=host, port=port)`;
  defaults `127.0.0.1:8000`, data dir `$HEARNARRO_DATA_DIR` or `./data`.

### e. The golden test's scoring path and the quality fixture test

**Golden** (`tests/test_ing4_reading_order_golden.py`):

1. Module import: skip the whole module if `tests/fixtures/pdfs/manifest.json` is missing;
   `ENTRIES` from the manifest.
2. `test_fixture_set_complete`: 20 entries, 5 per class (`academic`, `report`, `scanned`,
   `tables`), every PDF and `.expected.jsonl` present.
3. `test_reading_order_golden[name]`: `_skip_reason` skips scanned fixtures while
   `ocr_available()` is False; else `_score(name)` (cached with `functools.cache`):
   - expected: `prose_only((r["type"], r["text"]) for r in rows)` over the expected file;
   - actual: `ingest(FIXTURES / f"{name}.pdf", document_id=0, ocr=True)`, then
     `prose_only((block_type[s.block_id], s.text) for s in result.segments)`;
   - `word = word_score(actual, expected)`; `sentence = 1 - seq_levenshtein(actual, expected) / len(expected)`
     (diagnostic only); `ratio_actual = char_mass_ratio(actual, excluded_actual)`,
     `ratio_expected` likewise.
   Asserts `word >= PER_PDF_MIN` (0.95) and `char_mass_balanced(ratio_actual, ratio_expected)`
   (within `CHAR_MASS_TOLERANCE = 0.05`). Prints one tab-separated line per fixture.
4. `test_reading_order_mean`: mean of `word` over every scoreable fixture ≥ `MEAN_MIN` (0.97);
   prints the sentence-level mean too.

**Quality fixtures** (`tests/test_quality_fixtures.py`): `TEXT_FIXTURES` = manifest entries
whose class is not `scanned` (asserted to be 15 by `test_quality_fixture_count`). For each,
`check_pdf(FIXTURES / f"{name}.pdf", ocr=False)`; a check fails the test when
`not c.passed and c.count > ALLOWED.get((name, c.name), -1)`. So an informational check never
fails, a thresholded check fails unless an `ALLOWED` entry raises its count limit for that one
fixture, and a count above the pinned number fails ("Golden and quality gates").

### f. The smoke script's loop

`api/scripts/m1_smoke.py` drives a running `hearnarro serve` over HTTP with `httpx.Client`
(`--base-url`, default `http://127.0.0.1:8765`). It first `GET /documents`; unreachable → exit 2.
It imports the scoring from `tests/golden_util.py` (`sys.path` gets `api/`), so the gate and
the smoke share one definition.

- **Gate mode (default).** `run_gate(client, fixtures, classes, timeout) -> int`: manifest
  entries whose class is in `--classes` (default `academic,report,tables`; scanned needs OCR).
  For each: `upload` (`POST /documents`; 202 new, 200 "cached"), `wait_settled` (poll
  `GET /documents/{id}` every 0.2 s until `ready`/`failed` or `--timeout`, default 60 s),
  `all_segments` (follow `next_from` with `limit=500`), `score` (the golden's `prose_only`,
  `word_score`, `char_mass_ratio`), `quality` (`run_checks` on `QSeg(s["text"], s["type"])`
  with `max_page_chars=0`, so `empty_text_document` cannot fire over HTTP). A row passes when
  `word >= 0.95` and the mass guard holds. Exit 0 only when every fixture passed and the mean
  is ≥ 0.97. Throughput sums `page_count` and `parse_ms` over freshly parsed (202) documents.
  The quality line is printed but never changes the exit code.
- **`--one PDF`.** `run_one`: upload, wait, print pages / parse_ms / pages per second, the
  first 20 segments (`[type] text`), and the checklist. Exit 1 if not `ready`.
- **`--user-docs [DIR]`.** After the gate, `run_user_docs` uploads every PDF in DIR (default
  `api/tests/user_docs/`, git-ignored) and prints throughput, segment count and checks; no
  score, because user documents have no expected file.

## Modules and files

Signatures are copied from the files at `fa7b257`. Line counts are in
`_agent/results/294_m1_code_inventory.txt`.

### `api/hearnarro/ingestion/`

| File | Responsibility | Public functions / classes | Reads | Writes | Status |
| --- | --- | --- | --- | --- | --- |
| `__init__.py` | Package marker | none | none | none | implemented (empty) |
| `models.py` | Data model shared by every stage | `class BBox` (frozen: `x0, y0, x1, y1`; `width`, `height`, `x_mid`, `y_mid`, `def overlaps(self, other: BBox) -> bool`); `class Span`; `class Line` (`text` property); `BlockType` (Literal of 13 types); `class Block` (`text` property); `class Page`; `class LogicalBlock`; `class Segment` | none | none | tested |
| `extract.py` | Stage 1: glyphs → lines → blocks; tables, figures; OCR fallback (ING-2, D13) | `class OCRUnavailable(RuntimeError)`; `def ocr_available() -> bool`; `class LayoutChar` (frozen: `text, bbox, font, size, upright, mcid`); `def font_flags(font: str) -> tuple[bool, bool]`; `def page_from_layout(number: int, width: float, height: float, text_boxes: Sequence[LayoutBox], image_bboxes: Sequence[BBox] = (), table_bboxes: Sequence[BBox] = ()) -> Page`; `def figure_regions(image_bboxes: Sequence[BBox], drawing_rects: Sequence[BBox], page_width: float, page_height: float) -> list[BBox]`; `def retrack(line: list[LayoutChar]) -> list[LayoutChar]`; `def group_lines(chars: Sequence[LayoutChar]) -> list[list[LayoutChar]]`; `def group_blocks(lines: Sequence[list[LayoutChar]]) -> list[list[list[LayoutChar]]]`; `def is_math_line(line: Sequence[LayoutChar]) -> bool`; `def is_math_font(font: str) -> bool`; `def ligature_text(glyph: str) -> str \| None`; `def truetype_glyph_names(data: bytes) -> dict[int, str]`; `def repair_ligature(text: str, font: str, fixes: dict[tuple[str, str], str]) -> str`; `def rule_tables(rules: Sequence[BBox], page_height: float) -> list[BBox]`; `def has_columns(region: BBox, lines: Sequence[Sequence[LayoutChar]]) -> bool`; `def ocr_page(pdf_path: str \| Path, number: int) -> list[Block]`; `def extract_pages(pdf_path: str \| Path, *, ocr: bool = True, min_text_chars: int = 20, on_page: Callable[[int, int], None] \| None = None) -> list[Page]` | PDF (pdfplumber); page render (pypdfium2) for OCR | none | tested |
| `classify.py` | Stage 2: block types, first-match cascade plus passes (ING-3, D3, D12) | `def normalize_key(text: str) -> str`; `def body_median_size(pages: list[Page]) -> float`; `def repeated_band_texts(pages: list[Page], *, band_frac: float = BAND_FRAC, min_pages: int = 3) -> set[str]`; `def in_figure(block: Block, regions: list[BBox]) -> bool`; `def classify_pages(pages: list[Page]) -> list[Page]`; regexes `PAGE_NUMBER_RE`, `CONTACT_ONLY_RE`, `BOILERPLATE_RE`, `EMAIL` (imported by `merge.py`) | `list[Page]` | `Block.type`, `Block.lead`, block lines (fold, drop cap) in place | tested |
| `order.py` | Stage 3: reading order, two columns, inline fragments (ING-4, D2) | `READ_TYPES`; `def detect_columns(blocks: list[Block], page_width: float, *, gap_frac: float = GUTTER_FRAC, full_width_frac: float = 0.60) -> tuple[int, float \| None]`; `def attach_inline(blocks: list[Block]) -> list[Block]`; `def order_page(page: Page, *, gap_frac: float = GUTTER_FRAC, full_width_frac: float = 0.60) -> list[Block]`; `def order_document(pages: list[Page]) -> list[Block]` | `list[Page]` | `Block.inline` in place | tested |
| `merge.py` | Stage 4: line merge, de-hyphenation, cross-break joins (ING-5) | `def merge_lines(lines: list[str]) -> str`; `def is_noise_line(text: str) -> bool`; `def strip_emails(text: str) -> str`; `def merge_blocks(blocks: list[Block]) -> list[LogicalBlock]` | `list[Block]` | none | tested |
| `segment.py` | Stage 5: sentence split with offsets (ING-5, D4) | `def split_sentences(block: LogicalBlock, *, document_id: int, order_start: int, id_start: int) -> list[Segment]`; private `_segmenter() -> pysbd.Segmenter` (cached; also used by `merge.py`) | `LogicalBlock` | none | changing (tested at `fa7b257`) |
| `abbreviations.py` | Abbreviation data for the new splitter | not described (untracked) | | | changing (untracked) |
| `normalize.py` | Speech normalization with `char_map` (ING-6 subset) | `def normalize(text: str) -> tuple[str, list[int]]` | `str` | none | tested |
| `acronyms.py` | Acronym definitions per document (ING-6) | `MINOR`; `def find_definitions(text: str) -> dict[str, str]`; `def document_definitions(texts: Iterable[str]) -> dict[str, str]` | merged block texts | none (stored by `jobs._write_result` in `documents.acronyms_json`) | tested (`test_ing6_acronym_definitions.py`) |
| `pipeline.py` | Stage composition | `class IngestResult` (`pages`, `blocks`, `segments`, `acronyms`); `def ingest(pdf_path: str \| Path, *, document_id: int = 0, ocr: bool = True, on_page: Callable[[int, int], None] \| None = None) -> IngestResult` | PDF | none | tested |

#### `models.py`

Every stage communicates through these dataclasses and nothing else, so each stage can be
unit-tested with hand-built pages (`tests/conftest.py` `make_span`, `make_block`, `make_page`)
and replaced without touching its neighbours (Technical Design, "What this does not do in v1").
Coordinates are PDF points with the origin at the **top left** and y growing downward; stage 1
converts pdfminer's bottom-left coordinates once (`_Coords`) so no later stage thinks about it.
`BBox.overlaps` is strict (touching edges do not count); stage 1 has its own `_touch` for the
inclusive case. `Block.index` is the block's position in stage 1's list for its page and,
with `page`, identifies a raw block for the whole pipeline (`LogicalBlock.source`, the `blocks`
row bbox). Tested by `test_ing_models.py` (`test_ing3_bbox_dimensions`,
`test_ing3_bbox_overlaps`, `test_ing3_line_text_joins_spans`,
`test_ing3_block_text_is_raw_newline_joined`).

#### `extract.py`

Stage 1 exists because the extractor's own layout analysis is wrong for this job: pdfminer's
`LAParams` splits justified lines at wide word gaps and splits inline maths into separate
boxes (module comment, D13). So `extract.py` takes raw glyphs from pdfplumber in
content-stream order and groups them itself with rules that reproduce PyMuPDF's text device,
which the D11/D12 ground truth was drawn from. The constants at the top of the module are the
tuning surface; most say where they were measured (results 130, 131, 139). Pure helpers
(`group_lines`, `group_blocks`, `retrack`, `rule_tables`, `has_columns`, `figure_regions`,
`page_from_layout`, `truetype_glyph_names`) take plain sequences, so the tests drive them with
synthetic `LayoutChar` lists and never open a PDF; only `extract_pages`, `_layout_chars` and
the `_ligature_fixes` family touch pdfplumber/pdfminer objects. All vector and table analysis
is wrapped in `except Exception` and degrades to "no tables / no figures" on a damaged page
rather than failing the document. OCR (`ocr_page`) imports pypdfium2 and pytesseract lazily
and raises `OCRUnavailable` if called without them; `extract_pages` only calls it when
`ocr_available()`. The rules are in "Stage rules". Tested by `test_ing1_extract.py` (29 tests).

#### `classify.py`

Stage 2 assigns one type per block. The design point is that the **order of the tests is the
whole design** (guide, stage 2 caption): off-page, stamps and header/footer run before the size
rule, so a page number or running title is never promoted to a heading because it is large;
noise and the table region run before heading so a bold table header row or a letter-spaced
banner is never a heading. The body font size is a **document-wide** character-weighted median
(`body_median_size`), so a page of headings does not move it. Four passes then fix what a
per-block rule cannot see: cover pull quotes, vertical titles, drop caps (per page) and the
table of contents (whole document, because a TOC spans pages). Blocks are mutated in place;
`classify_pages` returns the same list. Tested by `test_ing2_classify.py` (53 tests).

#### `order.py`

Stage 3 turns typed blocks into one reading sequence per page (D2: geometric, no ML).
Column detection is a gutter search rather than a midpoint histogram, because a midpoint gap
alone accepts pages where text runs across the middle (`test_ing4_detect_columns_needs_a_gutter_not_just_a_midpoint_gap`).
`attach_inline` exists because the extractor emits inline maths as separate blocks whose
bboxes include sub/superscripts, so a top-y sort can put a fragment before its host or after
the next line; it re-chains fragments after their host line and marks them `inline` so stage 4
joins them (D12 rule 2). Footnotes are linearized separately and appended last on the page.
Tested by `test_ing3_order.py` (18 tests).

#### `merge.py`

Stage 4 is where text stops being geometry. It joins a block's lines into one string
(de-hyphenating), joins inline fragments into their host, and joins body text that a page or
column break interrupted mid-paragraph, letting floats (captions, tables, footnotes, figure
labels) stay where they are. It is also where noise *lines* inside a kept block are dropped
(email-only, boilerplate) and where page 0's author block loses its email tokens. It uses
pysbd through `segment._segmenter()` to move exactly one sentence past a float, so the split
point is the one stage 5 will produce. Tested by `test_ing4_merge.py` (25 tests).

#### `segment.py` (as of `fa7b257`; changing)

Stage 5 splits each `LogicalBlock.text` into sentences with pysbd
(`pysbd.Segmenter(language="en", clean=False, char_span=True)`, built once by `@cache`).
`clean=False` is required: cleaning rewrites text and would break offsets (D4). For each pysbd
span it strips whitespace, locates the sentence with `_locate` (pysbd's own offset when
`text[hint:hint+len(sent)] == sent`, else `text.find(sent, cursor)`), and raises `ValueError`
if the slice does not round-trip, so a bad offset fails the parse instead of producing a
highlight on the wrong words. Every `Segment` gets `text == block.text[char_start:char_end]`,
`section_id=None` (sections are M3), and `normalize(sent)`. Tested at `fa7b257` by
`test_ing5_segment.py` (5 tests: abbreviations, round-trip, messy whitespace, ids/orders/fields,
empty block). The working-tree rewrite adds an abbreviation-aware layer
(`abbreviations.py`); see the M2 map's "Sentence boundaries".

#### `normalize.py`

Normalization produces what the TTS model will read (`normalized_text`) without changing what
the reader displays (`text`); `char_map[k]` is the index in `text` of output character `k`, so
M2 can translate word timestamps back to display offsets. It is one left-to-right regex pass,
so offsets are monotone by construction. Rules in "Stage rules". Tested by
`test_ing6_normalize.py` (11 tests, including `test_ing6_char_map_invariants`).

#### `pipeline.py`

Composition only: no rule lives here. `on_page` is forwarded to `extract_pages` and does not
change the result (`test_ing1_ingest_passes_on_page_through_and_none_is_unchanged`). It is the
single entry point used by the worker (`jobs.run_ingestion`), the CLI, the quality checklist
and the golden test, which is what makes the golden score a statement about production output.

### `api/hearnarro/quality.py`

| File | Responsibility | Public functions / classes | Reads | Writes | Status |
| --- | --- | --- | --- | --- | --- |
| `quality.py` | Document quality checklist over output segments | `class QSeg` (frozen: `text: str`, `type: str`); `class CheckResult` (`name, count, threshold: float \| None, passed, examples, value`; `to_dict`); `class QualityReport` (`source, title, segments, checks`; `passed` property; `to_dict`; `table() -> str`); `check_dangling_hyphens`, `check_tracked_lines` (regex checks); `def check_ligature_artifacts(segs: Sequence[QSeg]) -> CheckResult`; `check_leader_dots`, `check_single_letter_segments`, `check_chapter_number_segments`, `check_midsentence_breaks`, `check_toc_leak`, `check_punctuation_only`, `check_duplicate_runs` (same signature); `def check_title_filename_like(title: str \| None, segs: Sequence[QSeg]) -> CheckResult`; `def check_empty_text_document(segs: Sequence[QSeg], *, max_page_chars: int) -> CheckResult`; `def run_checks(segs: Sequence[QSeg], *, title: str \| None, max_page_chars: int, source: str = "") -> QualityReport`; `def check_pdf(pdf_path: str \| Path, *, ocr: bool = True) -> QualityReport` | PDF (via `ingest`) or segments | none | tested |

The checklist exists because the golden score cannot see defects that do not change the word
stream much but are obvious to a listener (a stray "W" before "e start", "e!ect", a contents
page read aloud). Each check encodes a defect found on a user document (module docstring). It
looks only at what the pipeline outputs (segment text plus block type), so the same code runs
on `ingest` output (`check_pdf`) and on API output (`m1_smoke.py`). Tested by
`test_quality.py` (15 unit tests) and `test_quality_fixtures.py` (16: the count and 15 fixtures).

### `api/hearnarro/cli.py`, `api/hearnarro/__main__.py`

| File | Responsibility | Public functions / classes | Reads | Writes | Status |
| --- | --- | --- | --- | --- | --- |
| `cli.py` | `dump`, `check`, `serve` subcommands | `def main(argv: Sequence[str] \| None = None) -> int`; private `_dump(pdf: str, *, jsonl: bool, ocr: bool) -> int`, `_check(pdf: str, *, as_json: bool, ocr: bool) -> int`, `_serve(data_dir: str \| None, host: str, port: int) -> int` | PDF | stdout | implemented |
| `__main__.py` | `python -m hearnarro` | runs `main()` | none | none | implemented |

The CLI has no test of its own; `check` is a thin wrapper over `check_pdf` (tested), `dump`
over `ingest` (tested), `serve` over `create_app` (tested through the API tests).

### `api/hearnarro/app.py` (M1 part)

| File | Responsibility | Public functions / classes | Reads | Writes | Status |
| --- | --- | --- | --- | --- | --- |
| `app.py` | FastAPI factory, lifespan, executors | `MAX_UPLOAD_BYTES = 100 * 1024 * 1024`; `INGEST_WORKERS = 2`; `def create_app(data_dir: Path \| None = None, *, max_upload_bytes: int = MAX_UPLOAD_BYTES, executor_factory: Callable[[], Executor] \| None = None, tts_backend: TTSBackend \| None = None, encoder: AudioEncoder \| None = None, lookahead: int \| None = None) -> FastAPI`; `def build_backend(settings: Settings) -> TTSBackend` (M2) | settings, data dir | data dir, `pdfs/`, database (migrations) | tested (M1 part, via `test_api_documents.py`) |

M1's part of the lifespan: create `pdfs/`, run `run_migrations(root)` on a thread, set
`app.state.engine`, `app.state.ingest_executor` (`executor_factory()` or
`ProcessPoolExecutor(max_workers=2)`), `app.state.ingest_tasks`, `app.state.ingest_seconds`.
`executor_factory` exists for tests that monkeypatch the ingestion function: a patch does not
cross into a spawned process, so those tests inject a thread pool (docstring). On shutdown the
ingestion pool is shut down with `wait=True, cancel_futures=True` and outstanding watch tasks
are cancelled. The synthesis wiring in the same lifespan is M2 (`docs/CODE_MAP_M2.md`).
`app.state.data_dir` and `app.state.max_upload_bytes` are set outside the lifespan so the
handler can read them.

### `api/hearnarro/routes/documents.py`

| File | Responsibility | Public functions / classes | Reads | Writes | Status |
| --- | --- | --- | --- | --- | --- |
| `routes/documents.py` | Document endpoints (ING-1) | `router`; `SEGMENTS_DEFAULT_LIMIT = 100`, `SEGMENTS_MAX_LIMIT = 500`, `CHUNK = 1024 * 1024`, `PDF_MAGIC = b"%PDF-"`; `async def get_conn(request: Request) -> AsyncIterator[aiosqlite.Connection]`; `POST /documents` `async def upload_document(request: Request, file: UploadFile, conn: Conn) -> Any`; `GET /documents` `async def list_documents(conn: Conn) -> list[dict[str, Any]]`; `GET /documents/{document_id}` `async def get_document(document_id: int, conn: Conn) -> dict[str, Any]`; `GET /documents/{document_id}/segments` `async def get_segments(...) -> dict[str, Any]` | upload body; `documents`, `segments`, `blocks`, `sections` | `documents` row; `pdfs/{sha256}.pdf`; pool job | tested |

Flows (a) and (b). `routes/audio.py` and `routes/voices.py` are M2.

### `api/hearnarro/storage/`

| File | Responsibility | Public functions / classes | Reads | Writes | Status |
| --- | --- | --- | --- | --- | --- |
| `__init__.py` | Package marker | none | none | none | implemented (empty) |
| `db.py` | Data dir, engines, migrations, `char_map` codec (D7, D9) | `DATA_DIR_ENV = "HEARNARRO_DATA_DIR"`, `DEFAULT_DATA_DIR = Path("./data")`, `DB_FILENAME = "hearnarro.db"`, `BUSY_TIMEOUT_MS = 10_000`, `PRAGMAS`; `def resolve_data_dir(data_dir: Path \| str \| None) -> Path`; `def db_path(data_dir: Path) -> Path`; `def pdf_dir(data_dir: Path) -> Path`; `def sync_url(path: Path) -> str`; `class Engine` (`def __init__(self, path: Path) -> None`; `async def connect(self) -> AsyncIterator[aiosqlite.Connection]`, an async context manager); `def engine(data_dir: Path) -> Engine`; `def connect_sync(path: Path \| str) -> sqlite3.Connection`; `def run_migrations(data_dir: Path) -> None`; `def pack_char_map(char_map: list[int]) -> bytes`; `def unpack_char_map(blob: bytes) -> list[int]` | env, database | database file, schema | tested |
| `repo.py` | Async queries over one connection | `DOCUMENT_COLUMNS`; `DuplicateDocument = sqlite3.IntegrityError`; `def now_iso() -> str`; `async def get_document(conn: aiosqlite.Connection, document_id: int) -> dict[str, Any] \| None`; `async def get_document_by_sha256(conn: aiosqlite.Connection, sha256: str) -> dict[str, Any] \| None`; `async def list_documents(conn: aiosqlite.Connection) -> list[dict[str, Any]]`; `async def insert_document(conn: aiosqlite.Connection, *, title: str, filename: str, sha256: str, status: str) -> int`; `async def set_status(conn: aiosqlite.Connection, document_id: int, status: str, fail_reason: str \| None = None) -> None`; `async def list_sections(conn: aiosqlite.Connection, document_id: int) -> list[dict[str, Any]]`; `async def count_segments(conn: aiosqlite.Connection, document_id: int) -> int`; `async def list_segments(conn: aiosqlite.Connection, document_id: int, from_order: int, limit: int) -> list[dict[str, Any]]` | `documents`, `sections`, `segments`, `blocks` | `documents` | tested |
| `jobs.py` | The ingestion job in the worker process | `PROGRESS_EVERY = 10`; `class PageProgress` (`def __init__(self, write: Callable[[int], None], every: int = PROGRESS_EVERY) -> None`; `def __call__(self, done: int, total: int) -> None`); `def pdf_page_count(pdf_path: str \| Path) -> int`; `def pdf_title(pdf_path: str \| Path) -> str \| None`; `FILENAME_TITLE_RE`; `TITLE_HEADING_WORDS = (2, 12)`; `def choose_title(meta_title: str \| None, first_heading: str \| None, filename: str) -> str`; `def mark_failed(db_file: str \| Path, document_id: int, reason: str, parse_ms: int \| None = None) -> None`; `def run_ingestion(db_file: str, document_id: int, pdf_path: str) -> float` | PDF | `documents`, `blocks`, `segments` | tested |
| `migrations/env.py` | Alembic environment | URL from the config (`run_migrations`) or `HEARNARRO_DATA_DIR`; raw DDL, no `target_metadata`, `render_as_batch=True` | config, env | none | tested (via `run_migrations`) |
| `migrations/versions/0001_initial_schema.py` | The D7 DDL verbatim | `revision = "0001"`; `DDL` (6 tables + `segments_doc_order`); `upgrade`, `downgrade` | none | schema | tested; run by hand (225) |
| `migrations/versions/0002_parse_progress.py` | `pages_done`, `parse_ms` on `documents` | `revision = "0002"`, `down_revision = "0001"`; `upgrade` (two `ALTER TABLE ... ADD COLUMN`), `downgrade` (batch drop) | none | schema | tested; run by hand (225) |

**Why aiosqlite directly.** `Engine` is a connection factory, not SQLAlchemy's async engine,
because SQLAlchemy's async layer requires greenlet (MIT AND PSF-2.0), outside the licence rule
(`db.py` docstring). SQLAlchemy is used only synchronously, inside Alembic. **Why a blocking
connection in the worker.** The worker is a separate process with no event loop; `connect_sync`
applies the same pragmas so both sides agree on WAL and the busy timeout. **Why `run_ingestion`
is module-level.** It must pickle by reference into a spawned worker (`jobs.py` docstring).
`_agent/results/225_alembic.txt` shows both an upgrade from 0001 to head and a fresh database
to head ending at `0002 (head)`.

### `api/scripts/`

| File | Responsibility | Public functions / classes | Reads | Writes | Status |
| --- | --- | --- | --- | --- | --- |
| `m1_smoke.py` | HTTP end-to-end smoke and gate re-check | `DEFAULT_CLASSES = "academic,report,tables"`, `PER_PDF_MIN = 0.95`, `MEAN_MIN = 0.97`, `PAGE_LIMIT = 500`; `def upload(client: httpx.Client, pdf: Path) -> tuple[int, int]`; `def wait_settled(client: httpx.Client, doc_id: int, timeout: float) -> dict[str, Any]`; `def all_segments(client: httpx.Client, doc_id: int) -> list[dict[str, Any]]`; `def pages_per_s(pages: int \| None, parse_ms: int \| None) -> float \| None`; `def throughput_cells(doc: dict[str, Any]) -> str`; `def quality(doc: dict[str, Any], segments: list[dict[str, Any]], name: str) -> QualityReport`; `def checks_cell(report: QualityReport \| None) -> str`; `def print_failing(reports: list[QualityReport]) -> int`; `def score(segments: list[dict[str, Any]], expected_path: Path) -> tuple[float, float, float]`; `def run_gate(client: httpx.Client, fixtures: Path, classes: set[str], timeout: float) -> int`; `def run_user_docs(client: httpx.Client, folder: Path, timeout: float) -> None`; `def run_one(client: httpx.Client, pdf: Path, timeout: float) -> int`; `def main(argv: list[str] \| None = None) -> int` | manifest, fixture PDFs, expected files, the server | stdout | implemented (runs 170, 248) |
| `check_licences.py` | Licence classifier for the installed environment (CLAUDE.md policy) | `def classify(text: str) -> str`; `def classify_options(options: list[str]) -> str`; `def inspect(dist: md.Distribution) -> Row`; `def scan(allow: set[str] \| None = None) -> list[Row]`; `def violations(rows: list[Row]) -> list[Row]`; `def main(argv: list[str] \| None = None) -> int` | installed distribution metadata | stdout | tested (classifier); environment scan red (env) |

`check_licences.py` was committed during M2 (`d5844c0`) but enforces a rule that binds M1's
dependencies, so it is listed here.

### `api/tests/` (M1 files)

| File | What it covers | Requirement IDs | Status |
| --- | --- | --- | --- |
| `__init__.py` | Package marker (tests import `tests.golden_util`) | none | implemented (empty) |
| `conftest.py` (M1 part) | `def union(boxes: Sequence[BBox]) -> BBox`; `def make_span(text: str, x0: float, y0: float, x1: float, y1: float, size: float = 10.0, font: str = "Helvetica", bold: bool = False, superscript: bool = False) -> Span`; `def make_block(page: int, index: int, lines: Sequence[Sequence[Span]] \| Sequence[str], *, x0: float = 72.0, y0: float = 72.0, width: float = 468.0, size: float = 10.0, font: str = "Helvetica", bold: bool = False, type: BlockType = "body") -> Block`; `def make_page(number: int, blocks: list[Block], width: float = 612.0, height: float = 792.0, image_bboxes: Sequence[BBox] = (), table_bboxes: Sequence[BBox] = (), has_text_layer: bool = True, figure_bboxes: Sequence[BBox] = ()) -> Page` | ING-2..ING-5 helpers | implemented |
| `test_ing_models.py` | BBox geometry, Line/Block text | ING-3 | tested (4) |
| `test_ing1_extract.py` | Stage 1 grouping, fonts, tables, figures, tracking, ligatures, OCR flag, `on_page` | ING-1, ING-2, ING-3, ING-4 | tested (29) |
| `test_ing2_classify.py` | Every cascade rule and pass | ING-3 | tested (53) |
| `test_ing3_order.py` | Columns, linearization, inline fragments, unread types | ING-4 | tested (18) |
| `test_ing4_merge.py` | Line merge, hyphens, cross-break joins, floats, noise lines, emails, inline joins, gated same-page joins | ING-5 | tested (25) |
| `test_ing5_segment.py` | Sentence split and offsets (at `fa7b257`) | ING-5 | changing (5 at `fa7b257`) |
| `test_ing6_normalize.py` | Normalization rules and `char_map` invariants | ING-6 | tested (11) |
| `golden_util.py` | D12/D14 scoring helpers | ING-4 | tested (via `test_golden_util.py`) |
| `test_golden_util.py` | Edit distance, prose filter, tokenizer, score, mass guard | ING-4 | tested (12) |
| `test_ing4_reading_order_golden.py` | **M1 gate** | ING-4, ING-5 | tested (17 passed, 5 skipped without OCR) |
| `test_quality.py` | Each checklist check, false-positive exclusions, overall pass | ING-4, ING-5, ING-6 | tested (15) |
| `test_quality_fixtures.py` | Checklist over the 15 text fixtures with the pinned `ALLOWED` | ING-1..ING-6 | tested (2 test functions, 16 cases) |
| `test_api_documents.py` | HTTP contract: 202/200/413/415/404, pool of two, paging, failure paths, progress, title | ING-1 | tested (15) |
| `test_licences.py` | Licence classifier and environment scan | CLAUDE.md licensing | 2 tested, 1 red (env) |
| `boundary_util.py` | Sentence-boundary metric (M2 truth, ING-5) | ING-5, SYN-1 | tested (via `test_boundary_util.py`) |
| `test_boundary_util.py` | Metric unit tests | ING-5 | tested (9) |
| `fixtures/pdfs/` | 20 PDFs, `*.expected.jsonl`, 15 `*.sentences.txt`, `manifest.json`, `README.md`, `ATTRIBUTION.md` | ING-4 gate | data |
| `fixtures/unit/` | `blank.pdf`, `text.pdf`, `README.md` (stage 1 and API tests) | ING-1, ING-2 | data |

Per-file test counts are from the `def test_` names at `fa7b257`; parametrized tests count
once here and per case in result 296.

## Data structures

### Stage 1 types (`models.py`)

```python
@dataclass(frozen=True)
class BBox:
    """Axis-aligned box in PDF points, origin top-left, y grows downward."""
    x0: float
    y0: float
    x1: float
    y1: float

@dataclass
class Span:
    text: str
    bbox: BBox
    font: str            # subset prefix ("ABCDEF+") stripped
    size: float
    bold: bool = False   # from the font name (font_flags)
    italic: bool = False
    superscript: bool = False

@dataclass
class Line:
    spans: list[Span]
    bbox: BBox
    dir: tuple[float, float] = (1.0, 0.0)  # reading direction; anything else is rotated text

@dataclass
class Block:
    page: int            # 0-based page number
    index: int           # position in stage 1's block list for that page
    bbox: BBox
    lines: list[Line]
    type: BlockType = "body"
    ocr: bool = False    # True when produced by OCR (ING-2)
    inline: bool = False # set by stage 3: continues the previous block's text line (ING-4)
    lead: bool = False   # set by stage 2: read first on its page (a folded vertical title)

@dataclass
class Page:
    number: int
    width: float
    height: float
    blocks: list[Block]
    image_bboxes: list[BBox] = field(default_factory=list)
    table_bboxes: list[BBox] = field(default_factory=list)
    figure_bboxes: list[BBox] = field(default_factory=list)  # D12
    has_text_layer: bool = True
```

`Span` boundaries fall where `(font, size, upright, superscript)` changes inside a line
(`_line_from_layout`). A rotated line has `dir == (0.0, 1.0)`; stage 2 reads that.
`BlockType` is `heading, body, caption, footnote, header, footer, table, equation, list,
image, noise, figure, toc`. Read aloud (stage 3 `READ_TYPES`): `body, heading, list, caption,
equation, table`, plus `footnote` appended at the end of each page. Never read: `header,
footer, noise, figure, toc, image`.

### `LayoutChar` (`extract.py`)

```python
@dataclass(frozen=True)
class LayoutChar:
    text: str
    bbox: BBox | None      # None: a virtual space inserted between words
    font: str = ""
    size: float = 0.0
    upright: bool = True
    mcid: int | None = None  # marked-content id (tagged PDFs)
```

Stage 1's private currency. `LayoutLine = Sequence[LayoutChar]`, `LayoutBox = Sequence[LayoutLine]`.
A virtual space carries no geometry and joins the surrounding span's text. `mcid` is what
tells a tagged PDF (Word, Acrobat) from an untagged one (TeX) for the indent rule.

### `LogicalBlock` (`models.py`)

```python
@dataclass
class LogicalBlock:
    """Output of stage 4: one readable unit after line/page merging."""
    id: int                       # 0..N-1, reading order across the document
    page: int                     # page of the first source block
    type: BlockType
    text: str                     # merged text (lines joined, de-hyphenated, cross-page joined)
    source: list[tuple[int, int]] # (page, block.index) of every raw block merged in
```

Stored as one `blocks` row (`"order"` = `id`, `merged_text` = `text`, bbox of `source[0]`).

### `Segment` (`models.py`)

```python
@dataclass
class Segment:
    """One sentence; exactly TECHNICAL_DESIGN "Segment model"."""
    id: int
    document_id: int
    block_id: int
    order: int
    section_id: int | None
    text: str
    normalized_text: str
    char_start: int
    char_end: int
    char_map: list[int]
```

Invariants (tested): `text == block.text[char_start:char_end]`;
`len(char_map) == len(normalized_text)`; `char_map` is non-decreasing and every value is a
valid index into `text`. Three coordinate systems are pinned together here (guide, section 5):
block text (offsets `char_start`/`char_end`), segment text (what is displayed), normalized text
(what is spoken), with `char_map` from the third to the second.

### `IngestResult` (`pipeline.py`)

`pages: list[Page]`, `blocks: list[LogicalBlock]`, `segments: list[Segment]`.

### Quality types (`quality.py`)

`QSeg(text: str, type: str)`; `CheckResult(name, count, threshold, passed, examples, value)`
(`threshold=None` is informational and always passes; `examples` holds up to `MAX_EXAMPLES = 5`);
`QualityReport(source, title, segments, checks)` with `passed = all(c.passed for c in checks)`.

### Database rows (D7 DDL, migrations 0001 and 0002)

| Table | Columns M1 writes | Written by |
| --- | --- | --- |
| `documents` | `id`, `title`, `filename`, `sha256` (UNIQUE), `page_count`, `status` (`uploaded`/`parsing`/`ready`/`failed`, CHECK), `fail_reason`, `created_at`, and from 0002 `pages_done INTEGER NOT NULL DEFAULT 0`, `parse_ms INTEGER` | handler (insert, `parsing`, watcher `failed`); worker (counts, progress, `ready`/`failed`, title) |
| `blocks` | `document_id` (FK, cascade), `page`, `"order"`, `type`, `x0, y0, x1, y1`, `merged_text` | worker |
| `segments` | `document_id` (FK, cascade), `block_id` (FK), `section_id` (NULL), `"order"`, `text`, `normalized_text`, `char_start`, `char_end`, `char_map BLOB` (packed uint16) | worker |
| `sections` | created, never written in M1 | none |
| `audio_cache`, `settings` | created by 0001 for M2/M3 | none in M1 |

Unique index `segments_doc_order ON segments(document_id, "order")` serves the paging scan.
`voice_id`, `speed`, `position_*`, `last_opened_at` exist on `documents` and are returned by
`GET /documents/{id}` but not written by M1.

### Files under the data dir

```
$HEARNARRO_DATA_DIR/            (default ./data; `serve --data-dir` overrides)
  hearnarro.db                  SQLite, WAL (+ -wal, -shm)
  pdfs/{sha256}.pdf             the uploaded bytes, named by content
```

### `char_map` encoding

`pack_char_map` stores `array("H", char_map)` little-endian (byte-swapped on a big-endian host);
a value above 65 535 raises `OverflowError`. A segment longer than 65 536 characters would
therefore fail its document's write (a sentence that long does not occur in the fixtures).

## Concurrency model

| Context | What runs there | May it block? |
| --- | --- | --- |
| asyncio event loop (uvicorn) | Every handler, `_watch_ingestion`, aiosqlite calls | No. The file write and migrations go to `asyncio.to_thread`. |
| aiosqlite's per-connection thread | The SQL of one request | Yes; one connection per request (`Engine.connect`). |
| `ProcessPoolExecutor(max_workers=2)` | `run_ingestion`: parse plus all its database writes | Yes; separate processes, separate GIL. |

**Why processes.** Parsing is CPU-bound pure Python (pdfminer); in a thread it would hold the
GIL and stall every request (D9). Two workers bound memory and CPU on a laptop while letting a
second upload start. **The status row is the contract** between handler and worker (guide,
section 5b): the handler writes `uploaded` then `parsing` before submitting, the worker writes
progress and exactly one terminal state, and the watcher writes `failed` only when the worker
could not. **SQLite.** WAL lets the worker write while the API reads; `busy_timeout=10000` makes
a writer wait rather than fail when the other side holds the write lock; the final write is one
transaction, so readers see either the old document or the complete new one.
**Re-parse.** `_write_result` deletes the document's old blocks and segments first, so running a
job twice for one id replaces rather than duplicates. **Shutdown.** The pool is shut down with
`cancel_futures=True` (queued parses are dropped and stay `parsing` in the database; see Open
items) and watcher tasks are cancelled.

## Stage rules

Every threshold below is copied from the named module at `fa7b257`. "Pinned by" names the test
(in the stage's test file) that fails if the rule changes.

### Stage 1: extract (`extract.py`)

**Glyph preparation (`_layout_chars`).**

| Rule | Constants | Pinned by |
| --- | --- | --- |
| Coordinates converted to top-left page space, as pdfplumber does (`_Coords`) | none | `test_ing2_extract_pages_text_layer` |
| A font whose usual glyph drop below the baseline exceeds `MAX_DESCENT = 0.8` sizes (TeX CMSY declares a descent near −0.96 em) is lifted to `NORMAL_DESCENT = 0.25`; per font, not per glyph, so superscript rise survives | 0.8, 0.25 | `test_ing2_font_drops_lift_cmsy_boxes_only` |
| `(cid:N)`: `chr(N)` when N < 127 (CMEX delimiters become control characters, kept as equation segments, as PyMuPDF did), else dropped | 127 | (golden) |
| Ligature repair: for simple TrueType fonts with a ToUnicode map, glyph names from the embedded font's `cmap` + format-2 `post` tables; a code whose mapped text is one ASCII non-alphanumeric character and whose glyph is a ligature (`f_i`, `fi`, `uniFB01`, any AGL `x_y[_z[_w]]` of single letters) is replaced by the letters; a (font, char) pair two fonts disagree on is dropped | none | `test_ing2_ligature_glyph_names_map_to_letters`, `test_ing2_truetype_code_to_glyph_name_from_cmap_and_post`, `test_ing2_ligature_repair_replaces_only_mapped_punctuation` |
| Subset prefix `^[A-Z]{6}\+` stripped from font names | none | |
| Bold: `bold\|black\|heavy\|semibold\|demi\|medi\|cmbx` (case-insensitive) or a name ending `,B`/`-B`/`,BoldItalic`; italic: `italic\|ital\|oblique\|cmti` or `,I`/`-I`/`-It` | none | `test_ing2_font_flags`, `test_ing2_page_from_layout_span_flags_from_font_names` |

**Lines (`group_lines`, `_continues_line`).** Glyphs in content-stream order. A glyph continues
the current line when it has the same `upright` flag, overlaps the line's vertical extent by at
least `LINE_OVERLAP = 0.3` of the smaller height (accents are exempt: they sit above their
letter), and its horizontal gap from the previous glyph is within
`[-LINE_BACKSTEP × size, LINE_MAX_GAP × size]` = `[-0.5, 10.0]` font sizes. `OVERSTRIKE = True`: a
glyph stepping further back still continues the line if it starts no earlier than the previous
glyph minus 0.5 sizes (an accent then its letter, `/` over `∈`). A word space is inserted when
the gap exceeds `SPACE_GAP = 0.15` of the **next** glyph's size (`SPACE_NEXT_SIZE = True`, as
MuPDF does), or the baseline moves more than `BASELINE_JUMP = 0.8` sizes (stacked scripts,
limits), unless the previous glyph is "tight" (a spacing accent, or a CMSY/CMR glyph in
`_TIGHT_SYMBOLS` such as `∈ ≤ → −`; `=`, `|`, `×` keep their space). A real space glyph
becomes a virtual space. Pinned by `test_ing2_group_lines_keeps_justified_words_and_inserts_spaces`,
`test_ing2_no_word_space_after_tex_relation_but_after_equals`,
`test_ing2_stacked_scripts_are_read_with_a_space`, `test_ing2_overstrike_accent_stays_on_the_line`.

**Tracked text (`retrack`).** A line of at least `TRACKED_MIN_TOKENS = 6` tokens, at least
`TRACKED_SHARE = 0.7` of them single letters **but not all**, with no maths-font glyph, is
letter-spaced; a space between two fragments (one glyph, or a kerned capital pair such as
"OT") is kept only when its gap is at least `TRACKED_WORD_GAP = 2.0` × the median fragment gap.
A line of only single letters ("C O M P U T E R") is left for stage 2's banner rule. Pinned by
`test_ing2_tracked_caps_line_is_resplit_at_wide_gaps`,
`test_ing2_pure_letter_spaced_banner_is_left_for_the_noise_rule`,
`test_ing2_tracked_caps_kerned_pairs_and_trailing_words`,
`test_ing2_short_spaced_line_is_not_resplit`.

**Blocks (`group_blocks`), tested in this order for each line against the current block:**

1. **Maths/prose boundary.** If the line starts a new text row (no vertical overlap with the
   previous line) and exactly one of the two is a maths line, start a new block. A maths line
   holds a maths-font glyph (`MATH_FONT_MARKERS`: `Math, CMSY, CMMI, CMEX, CMBSY, MSBM, MSAM,
   RSFS, EUFM`) and its prose letters (text-font letters at ≥ `SCRIPT_RATIO = 0.8` of the
   dominant size) are under `MATH_LINE_PROSE = 0.3` of its glyphs. Pinned by
   `test_ing3_display_math_line_opens_its_own_block`.
2. **Way off the baseline.** Upright and the baseline is more than `PARA_BASELINE = 1.6` font
   sizes below the previous line's: new block, even if tall delimiters make the boxes touch.
3. **Overlap.** The line's bbox overlaps the block's bbox: join.
4. **Indent opens a block.** Upright, the line sits below the previous one
   (`y0 ≥ prev.y1 − 0.5 × size`) and starts more than `INDENT_NEW_BLOCK = 0.5` pt to its right,
   and any of: the PDF is tagged (either line has an `mcid`); the move is at most
   `UNTAGGED_INDENT_MAX = 2.0` pt (the previous line hung into the margin); the two lines are a
   centred pair (centres within `CENTRE_TOL = 3.0` pt, the second at least `CENTRE_INDENT = 5.0`
   pt narrower on the left: a title or author list); or the previous line is a reference entry
   (`^\[\d+\]`). Larger untagged moves are hanging indents of list items and wrapped headings
   and stay joined. Pinned by
   `test_ing4_tagged_indented_line_opens_block_untagged_hanging_indent_does_not`,
   `test_ing4_untagged_small_indent_opens_block`,
   `test_ing4_centred_title_lines_and_reference_entries_split`.
5. **Otherwise join** when the size ratio is ≤ `BLOCK_SIZE_RATIO = 1.25`, the vertical gap is
   within `[-0.5 × size, BLOCK_GAP × max size]` with `BLOCK_GAP = 0.5`, and the two overlap
   horizontally (for rotated text the axes swap). Pinned by
   `test_ing2_group_blocks_splits_on_gap_and_size`.

**Spans and superscripts (`_line_from_layout`).** A glyph is a superscript when its size is
≤ `SUPERSCRIPT_SIZE_RATIO = 0.75` × the line's dominant size and its bottom sits more than
`SUPERSCRIPT_RAISE = 0.2` dominant sizes above the dominant-size median baseline.

**Tables.** (a) `page.find_tables()` regions with at least 2 rows and at least 2 cells in some
row (a ruled frame around prose is one cell and is not a table). (b) Booktabs (`rule_tables`):
horizontal rules at most `RULE_MAX_HEIGHT = 1.5` thick and at least `RULE_MIN_WIDTH = 50.0` pt
wide; pieces at one y merge; a stack of ≥ `RULE_STACK_MIN = 3` rules whose ends align within
`RULE_ALIGN = 3.0` pt, each within `RULE_STACK_GAP = 0.5` of the page height of the next, bounds
a table, kept only if `has_columns`: at least `COLUMN_ROWS = 2` lines centred in it have a
glyph gap wider than `COLUMN_GAP = 1.0` font sizes. Pinned by
`test_ing3_booktabs_rule_stack_is_a_table_only_with_column_rows`.

**Figure regions (D12, `figure_regions`).** Every image bbox, plus each transitive union of
touching drawing rects (rects and lines; curves padded by `FIGURE_JOIN = 6.0` pt so arrows and
plot lines join their boxes) whose area is in `[FIGURE_MIN_FRAC, FIGURE_MAX_FRAC)` =
`[0.02, 0.80)` of the page. A thin wide rule never seeds a cluster. Padding plain rects too
merged report text boxes into "figures" (result 139, module comment). Pinned by
`test_ing3_figure_regions_curves_join_nearby_parts_rules_never_seed`,
`test_ing2_extract_pages_image_becomes_image_and_figure_bbox`.

**OCR fallback.** A page with fewer than `min_text_chars = 20` stripped characters:
`has_text_layer = False`, blocks cleared, and with `ocr=True` and `ocr_available()` (pytesseract
importable **and** `tesseract` on PATH) the page is rendered at `OCR_DPI = 300` with pypdfium2
and `pytesseract.image_to_data` words are grouped by `(block_num, par_num)` into blocks and by
`line_num` into lines, `ocr=True`, `font="ocr"`, size = word height. Pinned by
`test_ing2_extract_pages_blank_page_without_ocr`, `test_ing2_ocr_available_returns_bool`.

### Stage 2: classify (`classify.py`)

Document-wide inputs: `median = body_median_size(pages)` (span sizes weighted by text length)
and `repeated = repeated_band_texts(pages)` (normalized texts of top/bottom-band blocks on
≥ 3 distinct pages; band = `BAND_FRAC = 0.08` of the page height). Pinned by
`test_ing3_body_median_size_is_document_wide_and_char_weighted`,
`test_ing3_repeated_band_texts_needs_three_pages`, `test_ing3_normalize_key_keeps_digits`.

**The cascade (`_classify`), first match wins:**

| # | Type | Rule | Pinned by |
| --- | --- | --- | --- |
| 1 | noise (off-page) | Less than `OFF_PAGE_INSIDE_FRAC = 0.5` of the bbox area inside `[0, width] × [0, height]` (zero area: centre outside), **unless** its largest span is ≥ `OFF_PAGE_KEEP_SIZE_RATIO = 1.0` × median (a back-cover tagline is kept, small-print blurb dropped; user decision 2026-10-16, results 206, 213) | `test_ing3_off_page_block_is_noise`, `test_ing3_off_page_block_kept_from_body_size`, `test_ing3_off_page_heading_sized_block_is_read_as_heading`, `test_ing3_block_below_the_page_is_noise` |
| 2 | noise (margin stamp) | Some line rotated (`dir` not `(1, 0)`) and the block lies in the outer `MARGIN_FRAC = 0.10` of the page width (arXiv stamps); rotated text inside the page (axis labels) falls through | `test_ing3_rotated_margin_stamp_is_noise_but_rotated_figure_label_is_not` |
| 3 | header / footer | In the top or bottom band (bbox inside 8 %, or midpoint inside 8 %) **and** (text in `repeated`, or `PAGE_NUMBER_RE` (digits, roman, `page N…`, `N of M`), or midpoint in band and it looks like a running header: ≤ `BAND_MAX_LINES = 3` lines and ≥ `BAND_UPPER_RATIO = 0.6` upper-case letters or largest size ≤ `BAND_SMALL_RATIO = 0.95` × median). Top → header, bottom → footer | `test_ing3_header_rule_wins_over_heading_size`, `test_ing3_page_number_regex_matches`, `..._rejects`, `..._matches_roman`, `test_ing3_page_numbers_in_band_are_header_footer_but_not_outside`, `test_ing3_single_page_running_header_in_top_band` |
| 4 | body | Empty text | |
| 5 | noise (text) | All lines are leader lines (only `. · …` and spaces, ≥ `LEADER_MIN_DOTS = 3` dots); or punctuation only (not a bare `.,;:!?`, left to the equation rule); or every line is email/URL-only or boilerplate (`Preprint.`, `Under review.`, `This publication is available free of charge from…`); or every line is a rule (`[_\-–—=\s]{5,}`); or, on the first `COVER_PAGES = 2` pages, a lone rotated text-font letter with no other block on its row within 3 × its height; or ≥ 6 tokens all single letters (letter-spaced banner); or, on cover pages, a block starting below `SIGNATURE_TOP_FRAC = 0.70` of the height matching `Department of Commerce\|\bSecretary\b\|\bDirector\b` | `test_ing3_boilerplate_lines_are_noise`, `test_ing3_leader_dot_line_is_noise_outside_a_toc_region`, `test_ing3_punctuation_only_block_is_noise`, `test_ing3_dash_attribution_is_not_punctuation_noise`, `test_ing3_cover_signature_block_is_noise_only_low_on_cover_pages`, `test_ing3_single_letter_block_on_cover_page_is_noise` |
| 6 | table (centred) | `TABLE_FIRST = True`: the block's centre is inside a table region (page 0 uses `_cover_tables`, below) | `test_ing3_table_region_wins_over_heading` |
| 7 | heading | Largest span ≥ `HEADING_SIZE_RATIO = 1.15` × median; or bold majority (by characters), ≤ `HEADING_MAX_WORDS = 12` words, not ending in `.` | `test_ing3_heading_by_font_size`, `test_ing3_heading_by_bold_short_no_period` |
| 8 | caption | Starts `Figure\|Fig.\|Table\|Listing` + digit **and** within `CAPTION_MAX_DIST = 40.0` pt of an image or table region | `test_ing3_caption_needs_nearby_image` |
| 9 | footnote | Largest span ≤ `FOOTNOTE_SIZE_RATIO = 0.85` × median, top at ≥ `FOOTNOTE_TOP_FRAC = 0.75` of the height, more than `FOOTNOTE_MIN_CHARS = 3` non-space characters; or opens with a superscript digit and its top is at ≥ `SUPERSCRIPT_FOOTNOTE_TOP_FRAC = 0.5` (above that it is an affiliation mark) | `test_ing3_footnote_by_small_size_low_on_page`, `test_ing3_footnote_by_leading_superscript_digit`, `test_ing3_tiny_small_print_block_low_on_page_is_not_a_footnote` |
| 10 | table (overlap) | bbox overlaps a table region | `test_ing3_table_by_table_bbox_overlap` |
| 11 | equation | A bare equation number `(\d+[a-z]?)`; or maths characters (maths font or `MATH_CHARS`) are more than half; or a maths-font glyph and prose letters (≥ 0.8 × largest size) under `EQ_PROSE_LETTERS = 0.5` of non-space characters | `test_ing3_equation_by_math_font_or_symbols`, `test_ing3_equation_by_low_prose_share`, `test_ing3_bare_equation_number_is_equation` |
| 12 | list | First line matches `ITEM_RE` (`models.py`, shared with merge): a glyph from `BULLET_GLYPHS` (`•·▪▫■□●○◦‣►▶➢➤→⇒✓✔✗✘★☆`), or `-` `–` `*` before a space, or `\d+` / one lowercase letter / `ii`–`xiii` roman then `.` or `)` (or in parentheses) before a space; `—` is excluded (`— Wired` stays body) | `test_ing3_list_items`, `test_ing3_list_arrow_items_and_wrapped_items`, `test_ing3_every_bullet_glyph_starts_an_item`, `test_ing3_not_an_item_line`, `test_ing3_hyphenated_word_at_line_start_is_body` |
| 13 | body | Everything else | `test_ing3_plain_text_is_body` |

**Figure override (D12).** After the cascade, any block not typed caption whose bbox lies at
least `FIGURE_INSIDE_FRAC = 0.80` (by area) inside one figure region becomes `figure` (never
read). Pinned by `test_ing3_d12_block_inside_figure_region_is_figure`,
`test_ing3_d12_caption_inside_figure_region_stays_caption`,
`test_ing3_d12_half_overlap_is_not_figure`, `test_ing3_d12_figure_regions_union_and_area_bounds`.

**Cover tables (`_cover_tables`, page 0 only).** A table region whose member blocks hold no
digit, have at most `COVER_TABLE_MAX_LINES = 4` lines in all and are all heading-sized is a
ruled title frame and is dropped, so its blocks go through the cascade. Pinned by
`test_ing3_cover_digit_free_table_is_retyped_by_the_cascade`,
`test_ing3_cover_table_with_digits_or_off_cover_stays_table`.

**Per-page passes (in this order, after every block on the page is typed):**

1. **Cover pull quotes** (pages < 2): a run of consecutive blocks typed heading by the size rule
   whose joined text starts with an opening quote (`“ " ‘ « „`) or holds ≥
   `PULL_QUOTE_MIN_SENTENCES = 2` sentence ends becomes body. Pinned by
   `test_ing3_cover_pull_quote_run_is_body`, `test_ing3_cover_title_and_authors_stay_heading`.
2. **Vertical titles** (every page): ≥ `VSTACK_MIN = 5` single-letter blocks (types heading,
   body, noise, footnote, caption, list) whose x0 lie within `VSTACK_X_TOL = 10.0` pt, sorted by
   top and split where a gap exceeds `VSTACK_SPLIT = 2.0` × their median height, fold into one
   heading (first block, `lead = True`, read first on the page); a gap above
   `VSTACK_WORD_GAP = 1.5` × the median letter gap is a word break; the other letters become
   noise. Pinned by `test_ing3_vertical_letter_stack_becomes_one_heading_read_first`,
   `test_ing3_four_stacked_letters_are_not_a_vertical_title`.
3. **Drop caps** (every page): a heading or body block whose text is one capital `[A-Z]` with
   largest span ≥ `DROP_CAP_SIZE_RATIO = 1.5` × median is prepended to the body block whose
   first line starts inside the cap's vertical extent, at or right of the cap (1 pt slack),
   with a lowercase letter (topmost, then leftmost); the cap becomes noise. Pinned by
   `test_ing3_drop_cap_joins_the_paragraph_it_opens`,
   `test_ing3_big_letter_before_a_capitalised_block_is_not_a_drop_cap`.

**Document passes:**

1. **Table of contents (`_mark_toc`).** Over the document's blocks in page/block order (header,
   footer, figure, image and empty blocks skipped), a block of any type whose normalized text is
   `contents` or `table of contents` opens a region. TOC-like blocks (a single leader line or a
   single page-number-only line `^(?:\d{1,4}|[ivxlc]+)$`, or ≥ `TOC_LINE_SHARE = 0.5` of lines
   that are leaders, end in a 1–4 digit number, or hold ≥ 2 inner numbers) join it. Short blocks
   (≤ `TOC_LEAD_MAX_LINES = 2` lines, not a body-size-or-larger heading) join before the first
   TOC-like block, and after it only if they are not sentences and a TOC-like block follows
   within `TOC_LOOKAHEAD = 3` blocks (an entry title above its page number). The region ends at
   any other block, at a sentence (≥ `TOC_SENTENCE_MIN_WORDS = 4` words ending `.!?`), or after
   `TOC_MAX_PAGES = 6` pages. Only a region that saw a TOC-like block is typed `toc`; a
   "Contents" heading with no entries stays a heading. Pinned by
   `test_ing3_toc_heading_opens_region_typed_toc`,
   `test_ing3_toc_region_continues_across_pages_and_ends_at_real_heading`,
   `test_ing3_toc_region_ends_at_first_non_toc_block`,
   `test_ing3_toc_run_together_titles_and_page_numbers_block_is_toc`,
   `test_ing3_contents_heading_without_toc_lines_stays_heading`, `test_ing3_toc_is_not_read`,
   `test_ing3_body_typed_contents_with_page_number_blocks_is_toc`.
2. **Off-page re-check.** Off-page small print is re-typed noise after every pass, so a pass
   (pull quote, TOC) cannot resurrect it. Pinned by
   `test_ing3_off_page_small_print_beats_heading_rules`.

### Stage 3: order (`order.py`)

**Per page (`order_page`).** Readable = blocks in `READ_TYPES` (`body, heading, list, caption,
equation, table`) with non-empty text. `lead` blocks come first, by top y, and take no part in
column detection. Footnotes are collected separately and appended after the page's body, in
column order. Everything else (`header, footer, noise, figure, toc, image`) is dropped. Pinned
by `test_ing4_read_types`, `test_ing4_order_page_two_columns_drops_furniture_footnote_last`,
`test_ing4_order_page_skips_empty_blocks`, `test_ing4_order_page_drops_noise`,
`test_ing4_order_page_drops_figure_text`.

**Column detection (`detect_columns`).** Ignore blocks wider than `full_width_frac = 0.60` of
the page. One column if fewer than 2 narrow blocks, or narrow blocks hold under
`NARROW_SHARE = 0.5` of the page's text (weights are non-space characters, minimum 1). Every
integer x in the middle half `[0.25 W, 0.75 W]` is a candidate; its cost is the text of narrow
blocks straddling it, except blocks reaching more than `CROSS_SIDE_FRAC = 0.05` × W past it on
both sides (spanning text costs nothing). A candidate is acceptable when its cost is ≤
`CROSS_FRAC = 0.05` of the text and each side holds ≥ `SIDE_FRAC = 0.10`. Acceptable x with equal
cost form runs; two columns iff some run is at least `GUTTER_FRAC = 0.015` × W wide; the
cheapest (then widest) run wins and `split_x` is its centre. Pinned by
`test_ing4_detect_columns_two_clusters`, `..._one_cluster`, `..._small_gap_is_one_column`,
`..._ignores_full_width_blocks`, `..._needs_a_gutter_not_just_a_midpoint_gap`,
`..._ignores_blocks_spanning_the_gutter`.

**Linearization (`_linearize`).** One column: sort by `(y0, x0)`. Two columns: full-width
blocks (wider than 60 % of W, or reaching `BREAK_SIDE_FRAC` × W past `split_x` both ways) are
breaks, sorted by top; between consecutive breaks, the left column (midpoint < `split_x`) by
top, then the right column by top, then the break. Pinned by
`test_ing4_full_width_block_is_column_break`, `test_ing4_order_page_single_column_sorted_by_top`,
`test_ing4_order_document_concatenates_pages`.

**Inline fragments (`attach_inline`).** A host is a `body`/`list` block with at least
`INLINE_HOST_CHARS = 30` non-space characters (equation pieces never host). A fragment is a
`body`/`equation`/`list` block on the same page whose first text line overlaps the host's last
line vertically by ≥ `INLINE_OVERLAP = 0.8` of the shorter, is not centred more than
`INLINE_DROP = 0.4` font sizes below it (sum limits, fraction denominators stay put), and starts
within `[-INLINE_BACK, +INLINE_GAP]` = `[-0.75, +1.0]` font sizes of the line's end. The
leftmost such block among the next `INLINE_LOOKAHEAD = 10` is moved after the host, and the
search repeats from the fragment's end (a multi-line fragment's last line becomes the line).
A one-line fragment sorted just before its host (tie on top y) is moved after it. Every
fragment in the chain is marked `inline` (D12 rule 2). Pinned by
`test_ing4_attach_inline_moves_out_of_order_fragment_after_host`,
`test_ing4_attach_inline_fragment_sorted_before_host_follows_it`,
`test_ing4_attach_inline_in_order_chain_is_joined_d12`,
`test_ing4_attach_inline_ignores_hanging_and_distant_and_equation_hosts`.

### Stage 4: merge (`merge.py`)

**Lines (`merge_lines`).** Each line's whitespace collapsed; lines joined with one space. A
line ending in a visible hyphen (`-`, U+2010, U+2011) followed by a lowercase start loses the
hyphen and joins without a space; before an uppercase start the hyphen is kept with a space. A
soft hyphen (U+00AD) at a line end is always removed and the next line joined without a space;
one ending a block's last line is left for a cross-block join, then stripped at the end of
`merge_blocks`. Pinned by `test_ing5_merge_lines`, `..._unicode_hyphen_lowercase_dehyphenates`,
`..._unicode_hyphen_uppercase_keeps_hyphen`, `..._soft_hyphen_always_removed`,
`test_ing5_merge_blocks_soft_hyphen_at_line_end_always_removed`.

**Per block, in `merge_blocks`, in order:**

1. **Noise lines dropped.** Lines that are email-only (`EMAIL_ONLY_RE`) or match
   `BOILERPLATE_RE` (`is_noise_line`). Pinned by
   `test_ing5_merge_blocks_drops_email_only_and_boilerplate_lines`.
2. **Author-block emails.** On page 0, until a block starting `Abstract`, heading and body lines
   have email tokens removed (`{a, b}@host`, `a,b@host`, `a@host`) with dangling separators
   (`strip_emails`). Pinned by `test_ing5_merge_blocks_strips_emails_in_page0_author_block_only`.
3. **Inline join.** A block marked `inline` by stage 3 is appended to the previous logical
   block with `merge_lines` and its `(page, index)` added to `source`. Pinned by
   `test_ing5_merge_blocks_joins_inline_fragment_into_previous_block`,
   `test_ing5_merge_blocks_keeps_fragment_not_marked_inline`,
   `test_ing5_d12_inline_math_in_order_chain_joins_host`,
   `test_ing5_d12_inline_math_out_of_order_chain_joins_host`,
   `test_ing5_d12_display_equation_stays_separate`.
4. **Small-print float.** A body or heading block whose largest span is below
   `FLOAT_SIZE_RATIO = 0.85` × the last body block's, while a join candidate is open, is emitted
   as its own logical block and does not close the candidate (figure labels).
5. **Cross-break join.** A body block B joins the open candidate A (the last body logical block)
   when B is on A's page or the next, there is a flow break (`B.page != A.page` or B starts
   above A: a new page or a new column), and B continues A (`_continues`: B starts lowercase,
   or it is a page break and A does not end in `TERMINAL_PUNCT` `.!?:;"”’`). If floats lie
   between A and B, only B's first sentence (pysbd, `_first_sentence`) moves up into A and the
   rest of B becomes a new logical block after the floats (and the new candidate). Pinned by
   `test_ing5_merge_blocks_joins_sentence_across_page_break_past_footer`,
   `..._dehyphenates_across_page_break`, `..._dehyphenates_unicode_hyphen_across_page_break`,
   `..._lowercase_continuation_joins_even_after_period`,
   `..._keeps_separate_paragraphs_across_page_break`,
   `..._joins_sentence_across_column_break`, `..._does_not_join_within_a_column`,
   `..._moves_only_first_sentence_past_a_float`.
6. **Same-page paragraph join (gated per document).** Without a flow break, B joins the body
   block directly before it (no float between) when B starts within `PARA_JOIN_GAP = 1.0` of A's
   font sizes below A, B starts lowercase (or an opener `([{“‘"'` then lowercase), and A ends
   with a line-end hyphen or soft hyphen or without `PARA_TERMINAL` (terminal punctuation or
   `)`). This is on only when `_paragraph_joins_on`: the document has at least
   `PARA_JOIN_MIN_COUNT = 10` such candidate pairs **and** they are at least
   `PARA_JOIN_MIN_SHARE = 0.15` of its body blocks (the user book: 350 pairs, 0.23; golden
   fixtures at most 8 pairs, 0.13; result 195, module comment). The gate exists because the
   rule fixes one class of document (justified lines starting 0.5–2 pt apart, which stage 1
   reads as new blocks) and would wrongly merge real paragraphs elsewhere. Pinned by
   `test_ing5_same_page_fragments_join_when_a_is_unpunctuated_and_b_lowercase`,
   `test_ing5_same_page_no_join_after_terminal_punct_uppercase_or_heading`,
   `test_ing5_same_page_joins_only_when_systematic_in_the_document`.
7. **Blockers.** A heading, list or equation (`JOIN_BLOCKERS`) closes the candidate; any other
   non-body type (caption, table, footnote, image) is a float and leaves it open. Pinned by
   `test_ing5_merge_blocks_does_not_join_non_body`.
8. **List items (`split_items`).** A list block is split: each item line (`ITEM_RE`) plus the
   continuation lines after it is one `LogicalBlock` of type list (ids renumbered in order,
   every item's `source` is the list block), joined by `merge_lines`. `INLINE_ITEM_RE` splits a
   line before each `BULLET_GLYPHS` glyph with whitespace before it and a word, bracket or
   quote after it (`→ Education → The Story of AngelList` is two; `≥· · · ≥λd` is not split);
   a glyph alone on a line takes the next line. Pinned by
   `test_ing5_list_block_split_into_one_logical_block_per_item`,
   `test_ing5_list_items_split_across_page_break_are_not_joined`,
   `test_ing5_list_item_continuation_lines_join_their_item`, `test_ing5_inline_glyph_items_split`,
   `test_ing5_dash_star_and_numbered_items_split`,
   `test_ing5_glyph_alone_on_its_line_joins_the_next_line`,
   `test_ing5_dot_leader_ellipsis_in_a_list_item_is_not_split`.

Every raw block that is not joined becomes one `LogicalBlock`
(`test_ing5_merge_blocks_one_per_block_with_merged_lines`).

### Stage 5: segment (`segment.py` at `fa7b257`; changing)

| Rule | Pinned by |
| --- | --- |
| A list item (its own logical block, stage 4) is one segment unless it holds a sentence end mid-item; the glyph stays in `text`, `normalized_text` starts at the first word | `test_ing5_list_item_is_one_segment_glyph_silent`, `test_ing5_list_item_with_inner_sentence_end_splits`, `test_ing5_numbered_item_keeps_marker_spoken` |
| A block whose text is blank yields no segments | `test_ing5_split_sentences_empty_block` |
| pysbd `Segmenter(language="en", clean=False, char_span=True)`, one instance per process | `test_ing5_split_sentences_three_sentences_with_abbreviations` |
| Each span stripped; empty spans skipped; offset from pysbd when it round-trips, else `find` from the cursor; `ValueError` if `text[start:end] != sent` | `test_ing5_split_sentences_offsets_round_trip`, `..._offsets_round_trip_with_messy_whitespace` |
| `id = id_start + i`, `order = order_start + i`, `block_id = block.id`, `section_id = None` | `test_ing5_split_sentences_ids_orders_and_fields` |

The sentence-level score in result 151 (mean 0.9203 against 0.9914 word-level) is mostly
boundary disagreement (abbreviations, closing quotes split off); that is why the gate is
word-level (D14, results 70 and 146) and why the splitter is being rewritten in M2.

### Normalization (`normalize.py`)

First a leading bullet (`GLYPH_BULLET_RE` in `models.py`: whitespace, one or more
`BULLET_GLYPHS`, whitespace; or `-` `–` `*` and a space) emits nothing, so `→ Laughs a lot`
is spoken `Laughs a lot` with `char_map[0] == 2`; numbered markers (`1.`, `a)`, `(3)`) and a
mid-text glyph (`A → B`) are kept. Pinned by `test_ing6_leading_bullet_glyph_is_silent`,
`test_ing6_numbered_markers_and_non_bullets_are_spoken`.

Then one pass over `_PATTERN` matches, alternatives tried in this order:

| Match | Output | Example |
| --- | --- | --- |
| `citation` `\[\d+(?:\s*[,–-]\s*\d+)*\]` | dropped; if the output ends in whitespace and the next input character is whitespace, one of `,.;:!?)` or the end, that trailing space is removed too | `results [3, 5].` → `results.` |
| `etal` `\bet al\.` | `et al` | |
| `percent` `\b\d+(?:\.\d+)?%` | `<number> percent` | `3.2%` → `3.2 percent` |
| `url` `(?:\bhttps?://\|\bwww\.)[^\s/]+(?:/\S*)?` (one space allowed after `https://` or `www.` before a host, a PDF line break) | scheme and `www.` emit nothing; the host is spoken with `.` → ` dot `; a path of ≤ 3 plain segments (`[A-Za-z0-9_-]+`) and ≤ 30 chars is spoken with `/` → ` slash `, any other path or query is dropped; trailing `.,;:!?)]}'"”’` stays as text | `https://www.nist.gov/x.` → `nist dot gov slash x.`; `https://angel.co/syndicates` → `angel dot co slash syndicates` |
| `email` `[A-Za-z0-9._%+-]+@host.tld` (not after a word char, `.`, `+`, `-`) | `@` → ` at `, `.` → ` dot ` | `corporate@oreilly.com.` → `corporate at oreilly dot com.` |
| `domain` `(?:label\.)+(com\|org\|net\|io\|ai\|co\|edu\|gov\|dev\|app\|me\|us\|uk\|de\|fr\|ca\|info\|biz\|tv\|ly\|so\|xyz)` + optional `/path`, not after a word char or `@ . / : -`, not followed by a word char, `-` or `.letter`; the TLD must be lowercase (so `the end.So we` is not a domain) | as `url` | `Shopping.com.` → `Shopping dot com.`; `Twitter.com/Naval` → `Twitter dot com slash Naval`; `e.g.`, `3.2`, `Fig.2`, `v1.2.3`, `Nav.al` untouched |

`char_map`: unmatched characters map to themselves; an expansion of length L′ of a token at
`[start, start+L)` maps output character k to `start + min(L − 1, k × L // L′)` (monotone,
inside the token). A dropped citation contributes nothing. In a spoken address every character
of ` dot ` / ` slash ` / ` at ` maps onto that one source `.` / `/` / `@`, host and path letters
map to themselves, and a dropped scheme, `www.` or path maps to nothing, so highlighting stays
exact. Pinned by
`test_ing6_char_map_invariants`, `test_ing6_identity_on_plain_prose`,
`test_ing6_citation_dropped_and_space_collapsed`, `test_ing6_citation_list_and_range_dropped`,
`test_ing6_consecutive_drops_collapse_to_one_space`, `test_ing6_et_al`, `test_ing6_percent`,
`test_ing6_url_to_domain`, `test_ing6_www_url_keeps_host_and_short_path`,
`test_ing6_domain_spoken_with_dot`, `test_ing6_domain_char_map_points_at_source_letters`,
`test_ing6_www_maps_to_nothing`, `test_ing6_long_path_dropped`,
`test_ing6_email_spoken_with_at_and_dot`, `test_ing6_non_domains_untouched`,
`test_ing6_all_caps_tokens_left_for_the_backend`.

All-caps tokens are no longer rewritten here (until 2026-10-16 a `SPOKEN_ACRONYMS` allowlist
spelled every other 2–5 letter token, so "TED" became "T E D"). The synthesis backend decides
(`hearnarro/synthesis/acronyms.py`, CODE_MAP_M2). Documents ingested before the change still
carry the spelled form in `normalized_text` until re-ingested. `ingestion/acronyms.py` collects
definitions: `<words> (ACR)` or `ACR (<words>)` where the words spell ACR by initials (first word
capitalized; minor words such as "of" may supply a letter or be skipped); first definition per
ACR wins; "Figure 2 (left)" is rejected. `pipeline.ingest` stores them on `IngestResult.acronyms`,
`jobs._write_result` writes `documents.acronyms_json`, `GET /documents/{id}` returns `acronyms`. Numbers are not expanded to words (no `num2words` call
anywhere in M1; see "Dependencies and licences").

## Golden and quality gates

### The fixture set

`api/tests/fixtures/pdfs/` holds 20 PDFs (`manifest.json` fields: `name, class, two_column,
source, license, pages`), 5 per class: `academic` (two-column papers), `report` (single-column
NIST reports), `tables` (heavy tables and equations), `scanned` (2 rasterized pages, no text
layer). Text fixtures are trimmed to their first 4 pages (header/footer detection needs 3+
pages). `ATTRIBUTION.md` records source, licence and evidence for each. Each fixture has
`name.expected.jsonl`: one line per expected segment in reading order with `order, page, type,
text`, generated from the pipeline and hand-corrected once against the rendered pages, then
frozen (D11). The 15 text fixtures also have `name.sentences.txt` (M2 boundary truth: the same
prose word stream, one sentence per line). The scanned expected files are derived from their
source fixtures' pages 0–1 and are provisional until OCR lands (fixture README).

### How the word-level score works (`tests/golden_util.py`)

1. **Prose filter (D12).** `prose_only(items: Iterable[tuple[str, str]]) -> tuple[list[str], list[str]]`
   splits `(type, text)` pairs into kept texts (types in `PROSE_TYPES` = `heading, body, list,
   caption, footnote`) and excluded texts (everything else, chiefly `table` and `equation`,
   whose internals wait for ING-7), each whitespace-normalized by `norm`.
2. **Tokenizer (D14).** `words(texts: list[str]) -> list[str]`: join with spaces, lowercase,
   whitespace-split, strip `PUNCTUATION` (ASCII punctuation plus `‘ ’ “ ” – — …`) from both ends
   of each token, drop empties. Inner punctuation stays (`e.g`, `3.2`).
3. **Edit distance.** `seq_levenshtein(a: list[str], b: list[str]) -> int`, elements compared
   whole, unit costs.
4. **Score.** `word_score(actual_texts: list[str], expected_texts: list[str]) -> float` =
   `1 − seq_levenshtein(words(actual), words(expected)) / len(words(expected))`; raises if the
   expected side is empty. Segment boundaries do not affect it
   (`test_ing4_d14_segment_boundaries_do_not_matter`).
5. **Char-mass guard.** `char_mass_ratio(prose_texts, excluded_texts) -> float` = excluded
   characters / all characters; `char_mass_balanced(ratio_actual, ratio_expected) -> bool` is
   `abs(a − e) <= CHAR_MASS_TOLERANCE` (0.05). Without it, typing a difficult paragraph as
   `table` would remove it from both the error and the denominator.

**Why word-level.** The original D11 metric compared segment texts whole, so one sentence
split differently cost two whole segments regardless of whether the words were right and in
order. Result 70 shows the scores under the sentence-level definition (e.g. `academic_02` 0.7619);
result 146 shows the same pipeline output scored both ways (sentence 0.8571, word 0.9912 for
`academic_02`). Reading order is about the word stream; sentence boundaries are measured
separately in M2 (`boundary_util.py`).

**Thresholds.** `PER_PDF_MIN = 0.95` and `MEAN_MIN = 0.97` in both
`test_ing4_reading_order_golden.py` and `scripts/m1_smoke.py`; `CHAR_MASS_TOLERANCE = 0.05` in
`golden_util.py`.

### Last scores (`_agent/results/151_golden_d14.txt`)

| Class | Fixtures | Word-level range |
| --- | --- | --- |
| academic | 5 | 0.9839 – 0.9963 |
| report | 5 | 1.0000 (all) |
| tables | 5 | 0.9710 – 0.9989 |
| scanned | 5 | skipped (no OCR) |
| **mean (15)** | | **0.9914** (min 0.9710) |

### The quality checklist (`quality.py`)

Checks run on segments whose block type is not in `UNREAD_TYPES` (`header, footer, noise,
figure, toc, image`), except the single-letter and chapter-number checks, which look at
`PROSE_TYPES` (`heading, body, list, caption, footnote`). The module docstring numbers 11
checks with `chapter_number_segments` as a sub-item of 3; `run_checks` returns 12
`CheckResult`s. A thresholded count check passes when `count <= 0`.

| # | Check | Detects | Threshold |
| --- | --- | --- | --- |
| 1 | `dangling_hyphens` | `[A-Za-z][‐‑-] (?!(?:and\|or\|to\|nor)\b)[a-z]` ("inter- national"; a suspended hyphen "16K- and 65K-token" is excluded) | 0 |
| 2 | `ligature_artifacts` | `[A-Za-z][!#$%][a-z]` inside a token ("e!ect"), skipping URL/e-mail-like tokens (`://`, `www.`, `@`, or a `#` between letters in a token with `/` or an inner `.`) and a URL broken by a space | 0 |
| 3 | `single_letter_segments` | a prose segment that is one letter (a split drop cap) | 0 |
| 3a | `chapter_number_segments` | a prose segment that is one digit | informational |
| 4 | `tracked_lines` | `([A-Za-z] ){5,}[A-Za-z]` ("C H A P T E R") | 0 |
| 5 | `leader_dots` | `(\. ){4,}\|\.{5,}` in a segment that is ≥ `LEADER_MIN_SHARE = 0.6` dots and spaces (a maths ellipsis in prose is excluded) | 0 |
| 6 | `midsentence_breaks` | consecutive body segments, A without a sentence end `[.!?:;"”’)\]]$`, B starting lowercase (optionally after `([“'"‘`); value = hits / body segments | ratio ≤ `MIDSENTENCE_MAX_RATIO = 0.01` |
| 7 | `toc_leak` | segments ending in a page number within `TOC_WINDOW = 60` segments after a `contents` / `table of contents` segment | 0 |
| 8 | `punctuation_only` | segments with no letter or digit (mostly a closing quote split off by pysbd) | informational until M2 |
| 9 | `duplicate_runs` | identical consecutive texts of ≥ `DUPLICATE_MIN_CHARS = 12`, or a heading repeated within `HEADING_WINDOW = 20` segments | informational |
| 10 | `title_filename_like` | the chosen title matches `FILENAME_TITLE_RE` or has no whitespace, in a document with ≥ `MIN_SEGMENTS_FOR_TITLE = 5` segments | 0 |
| 11 | `empty_text_document` | some page has ≥ `TEXT_LAYER_MIN_CHARS = 200` characters but there are no segments | 0 |

Not checked: off-page text (stage 2 drops it before any segment exists, so it cannot be seen
afterwards). Results 206, 213 and 219 are the user-document before/after runs behind the
off-page, tagline and ligature rules (for example 219: `ligature_artifacts` 106 → 0 and
`single_letter_segments` 26 → 9 on one book).

**The pinned allowlist** (`tests/test_quality_fixtures.py` `ALLOWED`, re-pinned in result 246):

| Fixture | Check | Allowed count | Why (comment in the file) |
| --- | --- | --- | --- |
| `tables_04_markov_kernel` | `single_letter_segments` | 1 | a maths symbol "H" set as its own line |
| `academic_01_seahelm_audio` | `midsentence_breaks` | 2 | wrapped reference entries, inline maths, subfigure labels, some body splits (open parser issue) |
| `academic_02_memduet` | `midsentence_breaks` | 2 | same |
| `academic_04_legislative_xml` | `midsentence_breaks` | 2 | same |
| `tables_01_pfn_bayes` | `midsentence_breaks` | 9 | same |
| `tables_02_non_gaussian_sem` | `midsentence_breaks` | 13 | same |
| `tables_04_markov_kernel` | `midsentence_breaks` | 6 | same |
| `tables_05_decomposing_learner` | `midsentence_breaks` | 2 | same |

A count above the pinned number fails the test, so the allowlist ratchets: it can only be
lowered without a review.

### The smoke script's columns

Gate table (`run_gate`): `fixture`, `class`, `status` (`ready`, `cached` when the upload
returned 200, or the failing status), `pages` (`page_count`), `parse_ms` (the worker's wall
time from the database, not the client's), `pg/s`, `segs`, `word` (word score), `mass a/e`
(excluded char mass actual/expected), `checks` (`ok` or `N fail`), `result` (`pass`/`FAIL`).
Footer lines: fixtures passed/failed/skipped by class, the word-level mean and both gates,
`pages / parse time / throughput` over fresh documents only, `RESULT: PASS|FAIL`, and the
informational `quality:` count. User-documents table: `document, status, pages, parse_ms,
pg/s, segs, checks`. Result 170 is the run before the throughput and checks columns existed;
result 248 is the current shape (15/15, mean 0.9914, 17.1 pages/s, 7 documents with failing
checks, informational).

## Dependencies and licences

M1's runtime dependencies and their licences (`_agent/results/292_licences_table.txt` unless
stated):

| Package | Licence | Used for |
| --- | --- | --- |
| pdfplumber 0.11.10 | MIT | glyphs, fonts, images, rects/lines/curves, `find_tables` (stage 1) |
| pdfminer.six | MIT (D13; not in the 292 excerpt read) | underneath pdfplumber; `PDFTrueTypeFont`, `resolve1` for ligature repair |
| pypdfium2 5.14.0 | BSD-3-Clause, Apache-2.0 | page count and Info title (`jobs.py`), page rendering for OCR |
| pysbd 0.3.4 | MIT | sentence splitting (stage 5, and stage 4's first-sentence move) |
| fastapi 0.143.2 / starlette 1.8.0 | MIT / BSD-3-Clause | HTTP API |
| uvicorn 0.54.0 | BSD-3-Clause | server (`hearnarro serve`) |
| python-multipart 0.0.32 | Apache-2.0 | `UploadFile` parsing |
| pydantic 2.14.1 | MIT | FastAPI models |
| aiosqlite 0.22.1 | MIT | API database access (one connection per request) |
| alembic 1.20.0 / SQLAlchemy 2.1.4 | MIT / MIT | migrations only (synchronous) |
| httpx 0.28.1 (dev) | BSD-3-Clause | API tests, smoke script |
| pytesseract 0.3.13, pillow 12.3.0 (optional `ocr` extra) | Apache-2.0, MIT-CMU | OCR fallback when installed |

**Removed or avoided, and why:**

- **PyMuPDF (AGPL-3.0)**: the original D1 extractor. Replaced by pdfplumber + pypdfium2 in D13
  because AGPL is outside the Apache/MIT/BSD rule. Stage 1's grouping rules exist to reproduce
  PyMuPDF's line and block behaviour, because the hand-corrected ground truth was drawn from
  it. No M1 module imports `fitz` or `pymupdf`.
- **SQLAlchemy's async layer**: avoided because it requires greenlet (MIT AND PSF-2.0);
  aiosqlite is used directly (`db.py` docstring).
- **num2words (LGPL)**: **not removed at `fa7b257`.** It is still listed in
  `api/pyproject.toml` `dependencies` and installed, but no M1 module imports it
  (`normalize.py` does not expand numbers). The licence test treats it as a known violation
  "removed in M2 backend task" (`_agent/results/291_licences_test.txt`, `292`: `TOTAL 58
  VIOLATIONS 1 ['num2words']`). The PRD stack table still says "Custom rules + `num2words`".

**Licence test today.** In the current virtualenv `test_environment_has_no_licence_violations`
fails on two packages not in the 292 table, `Distance` (GPL) and `regex`
(`Apache-2.0 AND CNRI-Python`, classified unknown) (`_agent/results/296_m1_tests_at_head.txt`).
No M1 module imports either; who installed them was not checked (unverified; likely an M2
dependency survey or splitter experiment).

## How to run

All commands from `api/` with the project venv (`.venv`, Python 3.11).

```bash
cd api

# The M1 tests (310 passed, 5 skipped, 1 env failure at fa7b257, result 296)
.venv/bin/python -m pytest tests/test_ing_models.py tests/test_ing1_extract.py \
    tests/test_ing2_classify.py tests/test_ing3_order.py tests/test_ing4_merge.py \
    tests/test_ing5_segment.py tests/test_ing6_normalize.py tests/test_golden_util.py \
    tests/test_quality.py tests/test_quality_fixtures.py tests/test_api_documents.py -q

# The M1 gate with the per-fixture table
.venv/bin/python -m pytest tests/test_ing4_reading_order_golden.py -s -q

# Lint and format
.venv/bin/ruff check . && .venv/bin/ruff format --check .
```

CLI:

```bash
.venv/bin/python -m hearnarro dump tests/fixtures/pdfs/report_01_zero_trust.pdf | head
.venv/bin/python -m hearnarro dump --jsonl some.pdf > some.jsonl     # same format as expected.jsonl
.venv/bin/python -m hearnarro check some.pdf                          # exit 1 if a check fails
.venv/bin/python -m hearnarro check --json --no-ocr some.pdf
```

Server and smoke:

```bash
# Terminal 1: a fresh data dir makes every fixture a 202 (throughput is measured)
HEARNARRO_TTS_BACKEND=fake .venv/bin/python -m hearnarro serve --data-dir /tmp/hn-m1 --port 8765

# Terminal 2
.venv/bin/python scripts/m1_smoke.py --base-url http://127.0.0.1:8765
.venv/bin/python scripts/m1_smoke.py --user-docs                 # after the gate: tests/user_docs/*.pdf
.venv/bin/python scripts/m1_smoke.py --one ~/Downloads/paper.pdf

curl -s -F "file=@tests/fixtures/pdfs/report_01_zero_trust.pdf" http://127.0.0.1:8765/documents
curl -s http://127.0.0.1:8765/documents/1
curl -s "http://127.0.0.1:8765/documents/1/segments?from=0&limit=5"
```

`HEARNARRO_TTS_BACKEND=fake` is needed since M2 because the same lifespan builds the synthesis
service; M1 itself reads only `--data-dir` / `HEARNARRO_DATA_DIR`. Migrations run at start-up;
by hand: `HEARNARRO_DATA_DIR=/tmp/hn-m1 .venv/bin/alembic -c alembic.ini upgrade head`
(result 225).

## Open items

| Item | Where | Lands in |
| --- | --- | --- |
| Sentence splitter rewrite with an abbreviation table (in progress in the working tree) | `segment.py`, `abbreviations.py`, `test_ing5_segment.py` | M2 (boundary metric) |
| `punctuation_only` becomes thresholded with the boundary metric | `quality.py` | M2 |
| `num2words` (LGPL) still in `pyproject.toml` dependencies though unused by M1; PRD stack table still names it | `api/pyproject.toml`, `docs/PRD.md` | M2 backend task (per 291); PRD sync by the supervisor |
| Environment licence scan red on `Distance` (GPL) and `regex` (unknown) | venv; `test_licences.py` | whoever installed them (unverified) |
| Scanned fixtures skipped without Tesseract; expected files provisional | `test_ing4_reading_order_golden.py`, `fixtures/pdfs/scanned_*` | M4 (OCR fallback) |
| Table and equation internals excluded from the gate (D12) | `golden_util.PROSE_TYPES` | ING-7 (M4) |
| `midsentence_breaks` allowlist (36 pinned breaks over 7 fixtures) | `test_quality_fixtures.py` `ALLOWED` | open parser issue |
| `sections` never written; `section_id` always NULL | `segment.py`, `jobs.py` | M3 (LIB) |
| `BREAK_SIDE_FRAC = 9.0` in `order._is_break`: the docstring says a block straddling `split_x` by `CROSS_SIDE_FRAC` each way is full-width, but 9 × page width can never be reached, so only the 60 % width rule makes a break | `order.py` | review (code and Technical Design stage 3 text disagree) |
| Queued parses dropped at shutdown (`cancel_futures=True`) stay `parsing` in the database; nothing re-queues them at start-up | `app.py` lifespan | not scheduled |
| `char_map` uint16 caps a segment at 65 536 characters (`OverflowError` fails the document) | `db.pack_char_map` | not scheduled |
| CLI has no tests of its own | `cli.py` | not scheduled |
