# Testing M1 (ingest + skeleton) by hand

About 15 minutes. You start the API, drive one PDF through it with `curl`, compare the API
against the `dump` CLI, run the smoke script over all 15 text fixtures, and run the test
suite. M1 has no audio and no UI; what you are checking is that a PDF goes in and clean,
correctly ordered sentence segments come out (ING-1 to ING-5, gate in `docs/PRD.md`).

All commands run from `api/`. Use two terminals: one for the server, one for the rest.

## 1. Prerequisites

- [uv](https://docs.astral.sh/uv/) and Python 3.11 or newer.
- `curl`, `python3` and `sqlite3` on PATH (macOS ships all three).
- **No Tesseract needed.** Without it the 5 `scanned` fixtures produce no text (see section 7);
  everything else works.
- No GPU, no models, no ffmpeg: M1 does no synthesis.

First time only, create the environment:

```bash
cd api
uv venv --python 3.11 .venv
uv pip install --python .venv/bin/python -e ".[dev]"
```

## 2. Start the server (terminal 1)

```bash
cd api
export HN_DATA=$HOME/hearnarro-m1        # any empty directory; created if missing
.venv/bin/python -m hearnarro serve --data-dir "$HN_DATA" --port 8765
```

Without `--port` the server listens on 8000; without `--data-dir` it uses
`$HEARNARRO_DATA_DIR` or `./data`. It runs the database migrations at startup.

## 3. One PDF with curl (terminal 2)

```bash
cd api
export HN_DATA=$HOME/hearnarro-m1        # same directory as terminal 1
B=http://127.0.0.1:8765
```

| Step | Command | What you should see |
| --- | --- | --- |
| Empty library | `curl -s -w '\n%{http_code}\n' $B/documents` | `[]` then `200` |
| Upload | `curl -s -w '\n%{http_code}\n' -F file=@tests/fixtures/pdfs/report_01_zero_trust.pdf $B/documents` | `{"id":1,"status":"parsing"}` then `202` |
| Poll | `curl -s $B/documents/1 \| python3 -m json.tool` | `"status": "parsing"` at first, `"ready"` and `"page_count": 4` within a second or so; repeat until it is `ready` or `failed` (`fail_reason` says why) |
| List | `curl -s $B/documents \| python3 -m json.tool` | one entry, `status` `ready` |
| First page of segments | `curl -s "$B/documents/1/segments?from=0&limit=2" \| python3 -m json.tool` | `total: 57`, `next_from: 2`, two segments, the first `"type": "heading"`, `"text": "NIST Special Publication 800-207"` |
| Last page | `curl -s "$B/documents/1/segments?from=50&limit=100" \| python3 -c 'import json,sys; p=json.load(sys.stdin); print(p["total"], p["next_from"], [s["order"] for s in p["segments"]])'` | `57 None [50, 51, 52, 53, 54, 55, 56]` |
| Same bytes again (dedupe) | the upload command again | `{"id":1,"status":"ready"}` then `200` (no new document) |
| Not a PDF | `printf 'not a pdf\n' > "${TMPDIR:-/tmp}/notes.txt"` then `curl -s -w '\n%{http_code}\n' -F file=@"${TMPDIR:-/tmp}/notes.txt" $B/documents` | `only PDF uploads are supported`, `415` |
| Unknown id | `curl -s -w '\n%{http_code}\n' $B/documents/999` and `.../documents/999/segments` | `document not found`, `404` |

Paging rules: `from` is a segment `order` (0-based), `limit` defaults to 100 and is clamped
to 500, `next_from` is `null` on the last page. Each segment row carries `type` (the type of
the block it came from: `heading`, `body`, `list`, `caption`, `footnote`, `table`, ...),
`text` (what you read) and `normalized_text` (what TTS will say, e.g. `N I S T`).

## 4. Compare with the dump CLI

`dump` runs the same ingestion pipeline in-process, with no server and no database. The API
should store exactly what it prints:

```bash
.venv/bin/python -m hearnarro dump tests/fixtures/pdfs/report_01_zero_trust.pdf --jsonl > "${TMPDIR:-/tmp}/dump.jsonl"
curl -s "$B/documents/1/segments?limit=500" > "${TMPDIR:-/tmp}/api.json"
python3 -c 'import json,os; t=os.environ.get("TMPDIR","/tmp"); d=[(r["type"],r["text"]) for r in map(json.loads,open(t+"/dump.jsonl"))]; a=[(s["type"],s["text"]) for s in json.load(open(t+"/api.json"))["segments"]]; print(len(d),"dump segments,",len(a),"API segments, identical:",d==a)'
```

Expected: `57 dump segments, 57 API segments, identical: True`. To eyeball the reading order,
open the PDF next to `dump` output without `--jsonl`. To check a fixture against its golden
file, compare with `tests/fixtures/pdfs/<stem>.expected.jsonl`.

## 5. The smoke script: all 15 text fixtures over HTTP

With the server still running:

```bash
.venv/bin/python scripts/m1_smoke.py --base-url http://127.0.0.1:8765
```

For each `academic`, `report` and `tables` fixture it uploads the PDF (or gets the existing
id back), waits for `ready`, pages through every segment, and scores the result with the gate's
own code (`tests/golden_util.py`): only prose segments are kept (heading, body, list, caption,
footnote), and the score is 1 minus the word-level edit distance divided by the number of
expected words. Columns:

- `pages`, `parse_ms`, `pg/s`: the document's `page_count` and `parse_ms` from the API
  (wall time measured by the ingestion worker, not the client) and pages per second.
- `segs`: segments stored for the document.
- `word`: the score; the gate needs **0.95 per PDF** and **0.97 mean**.
- `mass a/e`: share of characters in table/equation segments, actual / expected; must agree
  within 0.05, so that calling prose a "table" cannot hide an error.
- `result`: `pass` or `FAIL`.

After the table, a total line sums pages and `parse_ms` over the fixtures:
`pages: N  parse time: X s  throughput: Y pages/s`. Sample (fresh data dir; timings vary by
machine):

```
fixture                            class     status  pages parse_ms   pg/s  segs    word      mass a/e  result
--------------------------------------------------------------------------------------------------------------
academic_01_seahelm_audio          academic  ready       4      307   13.0   214  0.9919 0.0903/0.0839  pass
...
tables_01_pfn_bayes                tables    ready       4      290   13.8   169  0.9779 0.0369/0.0388  pass
...
report_01_zero_trust               report    ready       4      161   24.8    57  1.0000 0.0000/0.0000  pass
...
--------------------------------------------------------------------------------------------------------------
fixtures: 15  passed: 15  failed: 0  skipped (class): 5
word-level mean: 0.9914 (gate >= 0.97); per-fixture gate >= 0.95
pages: 60  parse time: 3.5 s  throughput: 17.1 pages/s
RESULT: PASS
```

While a document parses, `GET /documents/{id}` shows `page_count` (set before extraction) and
`pages_done` (updated every 10 pages and at the last), so a client can show a percentage;
`parse_ms` is null until the document is `ready` or `failed`.

Exit code 0 means every fixture passed and the mean cleared 0.97. Options: `--classes report`
(one class only), `--timeout 60` (seconds per document), `--fixtures-dir`.

**Your own PDFs:** `--one` uploads any PDF and prints `pages / parse_ms / pages/s`, then its
first 20 segments with their types:

```bash
.venv/bin/python scripts/m1_smoke.py --one tests/fixtures/unit/text.pdf
.venv/bin/python scripts/m1_smoke.py --one ~/Downloads/some-paper.pdf
```

If the server is not running, the script says `cannot reach ...` and exits 2.

## Quality checklist

Run on any PDF (exit code 0 on PASS, 1 on FAIL; `--json` prints the structured result):

```
cd api
.venv/bin/hearnarro check path/to/book.pdf          # table
.venv/bin/hearnarro check path/to/book.pdf --json   # structured
.venv/bin/python -m pytest tests/test_quality.py tests/test_quality_fixtures.py -q
```

Code: `api/hearnarro/quality.py`. Each check reports a count, its threshold, PASS/FAIL and up
to five examples. The 15 text fixtures run in `tests/test_quality_fixtures.py`; known
fixture findings are pinned per fixture in its `ALLOWED` dict, each with a reason, so a
higher count fails.

1. `dangling_hyphens`: "inter- national" (hyphen, space, lowercase). Threshold 0.
2. `ligature_artifacts`: "e!ect", "di#erent". Threshold 0.
3. `single_letter_segments`: a prose segment that is one letter (split drop cap). Threshold 0.
   One-digit segments are counted as `chapter_number_segments`, informational.
4. `tracked_lines`: letter-spaced text ("C H A P T E R"). Threshold 0.
5. `leader_dots`: ". . . ." or "....". Threshold 0.
6. `midsentence_breaks`: body segment without a sentence end followed by one starting
   lowercase. Threshold: ratio to body segments at most 0.01.
7. `toc_leak`: within 60 segments after "Contents", segments ending in a page number. Threshold 0.
8. `punctuation_only`: segments with no letter or digit. Threshold 0.
9. `duplicate_runs`: the same segment twice in a row (12+ chars), or a heading repeated
   within 20 segments. Threshold 0.
10. `title_filename_like`: the chosen title looks like a file name. Threshold 0.
11. `empty_text_document`: a text layer (200+ chars on a page) but no segments. Threshold 0.

Off-page text leaks are not checked: stage 1 drops that text before segments exist.

## 6. The test suite

```bash
.venv/bin/python -m pytest -q                                      # everything
.venv/bin/python -m pytest -q tests/test_ing4_reading_order_golden.py   # the M1 gate alone
```

The gate test runs the same scoring in-process (no server). The 5 skips are the scanned
fixtures.

## 7. What the "scanned" skips mean

Five fixtures (`scanned_*`) are image-only PDFs. Reading them needs OCR (Tesseract), which is
deferred to M4. Without it they upload fine and end `ready` with **0 segments**:

```bash
curl -s -w '\n%{http_code}\n' -F file=@tests/fixtures/pdfs/scanned_01_seahelm_audio.pdf $B/documents
curl -s "$B/documents/2/segments" | python3 -c 'import json,sys; print("total segments:", json.load(sys.stdin)["total"])'
```

prints `total segments: 0`. The smoke script leaves the class out by default;
`--classes scanned` scores them and reports 5 `FAIL`s at 0.0000, which is expected today.

## 8. Where data lands, and how to reset

```
$HN_DATA/hearnarro.db            SQLite (WAL): documents, blocks, sections, segments, ...
$HN_DATA/pdfs/<sha256>.pdf       each uploaded PDF, named by the hash of its bytes
```

```bash
ls "$HN_DATA" "$HN_DATA/pdfs"
sqlite3 "$HN_DATA/hearnarro.db" 'select id, status, page_count, title from documents'
```

To reset: stop the server (Ctrl-C in terminal 1), then `rm -rf "$HN_DATA"` and start it
again. Ids restart at 1.

## 9. What good looks like

| Check | Expected |
| --- | --- |
| Upload | `202 {"id":1,"status":"parsing"}`, `ready` within about a second for a 4-page PDF |
| Re-upload same file | `200`, same id |
| `.txt` upload / unknown id | `415` / `404` |
| `report_01_zero_trust` | 4 pages, 57 segments, identical to `dump` |
| Smoke script | 15 rows, all `pass`, `fixtures: 15 passed: 15`, `word-level mean: 0.9914`, a `pages: 60  parse time: ... throughput: ...` line, `RESULT: PASS`, exit 0 |
| Lowest fixture | `tables_03_copula_subspaces` at 0.9710 |
| `report_*` fixtures | 1.0000 each |
| pytest | 0 failed; the scanned fixtures skipped |
