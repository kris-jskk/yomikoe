# HearNarro evals code map: runner, run records, compare (E0, E1)

This document explains how the eval layer works end to end and what every file under
`api/hearnarro/evals/` does. It is written for an engineer who has read `docs/PRD.md`,
`docs/TECHNICAL_DESIGN.md` (D31–D34) and the design `_agent/specs/evals-design.md` (the spec,
sections 3.1–3.6). Where the code and the spec differ, this map says what the code does and lists
the difference under "Spec deviations".

## Scope and status

**As of phase E0** on branch `m4-library`, updated 2026-10-17. E0 ships the runner, the run-record
store, compare/report and the two tier-0 suites that wrap scorers which already existed:

- **EVAL-1 Order** (ING-3/4/5): the reading-order word score of the M1 golden test, per fixture.
- **EVAL-2 Boundaries** (ING-5, SYN-1): sentence-boundary precision, recall and F1 of the M2
  boundary test, per fixture.

D31: an eval is a scored test with the threshold removed and the per-example score kept. The gate
tests (`api/tests/test_ing4_reading_order_golden.py`, `api/tests/test_syn_boundaries.py`) keep
their thresholds and remain the only merge blockers; evals are the trend line above the floor.

### Phase E1 (2026-10-17)

E1 adds the two remaining tier-0 suites and a `direction` per suite:

- **EVAL-3 Clean text** (ING-1..6): every check of `hearnarro.quality.check_pdf` on the 15 text
  fixtures, count and rate per 1 000 segment words, `total_rate` = sum of rates. Lower is better
  (`DIRECTION = "lower"`); `store.compare` flags a rise of more than 1 per 1 000 words.
- **EVAL-4 Speech form** (ING-6, ING-7, SYN-4): 302 authored pairs in
  `api/hearnarro/evals/data/speech_form.jsonl` (14 categories, 20–24 each), written text →
  what a careful narrator says, authored from the PRD rules and not from the normalizer's output.
  `spoken()` runs the app's own path: `merge_blocks` → `split_sentences` (which calls `normalize`
  and builds the ING-7 cues) → per segment `caps_fold_spans` and `decide` from
  `hearnarro.synthesis.acronyms`, in the order of `KokoroBackend._tokens`. Spelled acronyms are
  rendered as letters ("P D F"). Exact match on canonical words plus partial credit
  (1 − word edit distance / expected words).

Gate: 7 tests appended to `api/tests/test_eval_gate.py`; red `_agent/results/561_e1_gate_red.txt`
(7 failed), green `_agent/results/562_e1_gate_green.txt` (12 passed). Related tests
`_agent/results/565_e1_tests.txt` (374 passed); ruff `_agent/results/564_e1_ruff.txt`.

Tier-0 record `evals/runs/2026-10-17_0a00123.json` (console `_agent/results/563_e1_tier0_run.txt`,
13.3 s wall for EVAL-1..4): EVAL-3 total mean rate 2.5847 per 1 000 words (duplicate_runs 1.68,
midsentence_breaks 0.87); EVAL-4 accuracy 0.2748, partial mean 0.7099. Numbers, dates, times,
money, units and phone/range pairs score 0 exact: digits reach the voice as digits and are read by
misaki's G2P, which tier 0 does not model.

### The gate

`api/tests/test_eval_gate.py` (5 tests): one run of EVAL-1 + EVAL-2 into a temporary directory,
the record shape (spec 3.4), aggregates recomputed from the examples, `compare` of a record with
itself (zero deltas, no regressions) and with a copy whose first EVAL-1 example is lowered by 0.02
(exactly that example flagged, D33 tolerance 0.01). Red before the package existed:
`_agent/results/552_eval_gate_red.txt` (5 errors, `ModuleNotFoundError`); green:
`_agent/results/553_eval_gate_green.txt` (5 passed). The four existing scorer and gate test files
still pass after the scorer move: `_agent/results/554_eval_existing_tests.txt` (69 passed, 5
skipped: the scanned fixtures without tesseract).

### Baseline

`evals/runs/2026-10-17_eadaef6.json` (console output `_agent/results/556_eval_first_run.txt`):
EVAL-1 mean 0.9914, min 0.9710 (15 scored, 5 scanned skipped); EVAL-2 mean F1 0.9661, min recall
0.9722 (15 scored). Tier-0 wall time 9.25 s (EVAL-1 7.89 s including the PDF parses, EVAL-2
1.36 s reusing them).

### Status words

| Word | Meaning |
| --- | --- |
| implemented | Real code; exercised only indirectly or by hand. |
| tested | Real code plus a passing saved run that exercises it (553 gate, 554 existing tests). |
| planned | In the spec, not yet written. |

## Code flows

### a. `python -m hearnarro.evals run EVAL-1 EVAL-2 [--tier N] [--out DIR] [--baseline RUN_ID]`

```
CLI (__main__)        runner.run           suites.select / suite modules       store
  |-- parse args ------->|                        |                              |
  |   (--baseline: store.read_record) ------------------------------------------>|
  |                      |-- select(ids, tier) -->|                              |
  |                      |-- per suite: dataset() → score(example) → aggregate() |
  |                      |      (_fixtures.ingested: one ingest() per PDF, cached)
  |                      |-- write_record ------------------------------------->| <run_id>.json, latest.json
  |<-- record, path -----|                                                       |
  |-- store.compare(baseline, record) if --baseline; report.scorecard → stdout   |
```

1. **Parse.** `api/hearnarro/evals/__main__.py` → `main` builds the `run` and `compare`
   subcommands; `--out` defaults to `store.DEFAULT_RUNS_DIR` (repo-root `evals/runs/`).
2. **Select.** `suites/__init__.py` → `select(ids, tier)`: explicit ids in the order given
   (duplicates dropped, unknown ids raise `KeyError`), or `all` = every registered suite with
   `TIER <= tier`.
3. **Header.** `runner.py` → `run`: `run_id = <UTC date>_<git rev-parse --short HEAD>`,
   `date` (UTC, ISO), `config` from `_config` (`backend: "fake"`, `speed: 1.0`, `tesseract` from
   `hearnarro.ingestion.extract.ocr_available()`, `python`, `tier`).
4. **Score.** For each suite: `dataset()` yields `{id, class, skip}`; skipped examples go to
   `skipped` with their reason; the rest go through `score(example)`; `aggregate(examples)` gives
   the suite summary; wall time is stored as `seconds`.
5. **Parse once.** `suites/_fixtures.py` → `ingested(name)` calls
   `hearnarro.ingestion.pipeline.ingest(pdf, document_id=0, ocr=True)` and keeps the prose segment
   texts (D12, `scorers.prose_only`) and the D14 guard's excluded texts
   (`scorers.excluded_actual_texts`); `functools.cache` makes EVAL-2 reuse EVAL-1's parse.
6. **Write.** `store.py` → `write_record` writes `<out>/<run_id>.json` (indented JSON) and
   `<out>/latest.json` = `{"run_id", "file"}`. A second run on the same day and commit overwrites
   the file.
7. **Print.** `report.py` → `scorecard(record, comparison)`: per suite the scored/skipped counts,
   an aggregate table (with a Δ column when compared) and the worst example; then the regressions
   list. The record path is printed last.

### b. `python -m hearnarro.evals compare A B [--out DIR]`

1. `__main__.main` → `store.read_record` for each ref: an existing file path, `latest`
   (resolved through `latest.json`), or a run id (`<out>/<run_id>.json`).
2. `store.compare(a, b)` (D33), for each suite present in both records:
   - aggregate deltas `b − a` over the flattened numeric aggregates (`by_class.academic` etc.);
   - example deltas `b − a` for every numeric field of every example present in both;
   - one regression entry per example when a numeric field fell by more than the suite tolerance
     (`TOLERANCE`, 0.01 for both E0 suites), a boolean field went true → false (EVAL-1
     `char_mass_ok`), or the example is missing from `b` ("new failure").
3. `report.scorecard(b, comparison)` prints B's scorecard with the Δ column and the regressions.

## Modules and files

### `api/hearnarro/evals/`

| File | Responsibility | Public | Reads / writes | Status |
| --- | --- | --- | --- | --- |
| `__init__.py` | Package docstring (D31–D34) | none | none | implemented |
| `__main__.py` | argparse CLI: `run`, `compare` | `main` | stdout; records via `store` | tested (by hand, `556`) |
| `runner.py` | Runs the selected suites and writes one record | `run(suite_ids, out_dir=None, tier=0) -> (record, path)` | `git rev-parse`; fixtures via suites; record via `store` | tested (gate) |
| `store.py` | Record files, `latest.json` pointer, compare per D33; honours suite `direction` and compares nested example metrics under dotted keys (E1) | `DEFAULT_RUNS_DIR`, `LATEST`, `TOLERANCE`, `DEFAULT_TOLERANCE`, `write_record`, `read_record`, `compare` | `evals/runs/*.json` | tested (gate) |
| `report.py` | Markdown scorecard; the worst example is the highest score for a lower-is-better suite | `scorecard(record, comparison=None)`, `lines_for_compare(comparison)` | none | tested (by hand, `556`) |
| `scorers.py` | Pure scoring functions moved from `api/tests/golden_util.py` (D12/D14 word score, char-mass guard) and `api/tests/boundary_util.py` (boundary alignment, P/R/F1) | `PROSE_TYPES`, `CHAR_MASS_TOLERANCE`, `PUNCTUATION`, `norm`, `seq_levenshtein`, `prose_only`, `excluded_actual_texts`, `words`, `word_score`, `char_mass_ratio`, `char_mass_balanced`, `sentence_words`, `boundaries`, `align_boundaries`, `prf` | none | tested (`test_golden_util.py`, `test_boundary_util.py`, gate) |
| `suites/__init__.py` | Suite registry (EVAL-1..4) | `SUITES`, `select(ids, tier)`, `direction(suite_id)` | none | tested (gate) |
| `suites/_fixtures.py` | Fixture manifest, expected rows, truth sentences, one cached ingest per PDF | `FIXTURES`, `manifest`, `expected_rows`, `truth_sentences`, `ingest_result`, `ingested` | `api/tests/fixtures/pdfs/` (manifest, `*.pdf`, `*.expected.jsonl`, `*.sentences.txt`) | tested (gate) |
| `suites/eval1_order.py` | EVAL-1: 20 fixtures (scanned skipped without tesseract); score = `word_score`; `char_mass_ok` per example | `ID`, `TITLE`, `TIER`, `dataset`, `score`, `aggregate` (mean, min, by_class) | via `_fixtures` | tested (gate) |
| `suites/eval2_boundaries.py` | EVAL-2: 15 non-scanned fixtures; precision, recall, F1; score = F1 | `ID`, `TITLE`, `TIER`, `dataset`, `score`, `aggregate` (mean_f1, min_recall) | via `_fixtures` | tested (gate) |
| `suites/eval3_clean.py` | EVAL-3: 15 text fixtures; per check count and rate per 1 000 words; score = `total_rate`; `DIRECTION = "lower"` | `ID`, `TITLE`, `TIER`, `DIRECTION`, `dataset`, `score`, `aggregate` (mean_rate per check, total_mean_rate) | `hearnarro.quality.check_pdf`; word count from `_fixtures.ingest_result` | tested (gate) |
| `suites/eval4_speech_form.py` | EVAL-4: the dataset below through the app's text-to-voice path; exact and partial per pair | `ID`, `TITLE`, `TIER`, `DIRECTION`, `DATA`, `load_pairs`, `spoken(text, block)`, `canonical`, `dataset`, `score`, `aggregate` (accuracy, partial_mean, by_category) | `data/speech_form.jsonl`; calls `ingestion.merge`, `ingestion.segment`, `ingestion.acronyms`, `synthesis.acronyms`, `synthesis.lexicon_overrides` | tested (gate) |
| `data/speech_form.jsonl` | 302 pairs: `id`, `category`, `text`, `expected`, optional `note`, optional `block` (`heading`, `table`: rows by line, cells by ` \| `; `equation`) | n/a | n/a | tested (gate: shape, ≥ 15 per category) |
| `data/listening_rubric.md` | EVAL-9 form | n/a | n/a | planned |

### Test helpers and tests

| File | Responsibility | Status |
| --- | --- | --- |
| `api/tests/golden_util.py` | Re-exports the reading-order scorers from `hearnarro.evals.scorers` (no logic) | tested (`554`) |
| `api/tests/boundary_util.py` | Re-exports the boundary scorers (including `_alignment`) from `hearnarro.evals.scorers` | tested (`554`) |
| `api/tests/test_eval_gate.py` | E0 gate: record shape, aggregates, compare zero/one-regression cases; E1: registry direction, `all` under 60 s, EVAL-3 rates, lower-is-better compare, EVAL-4 dataset shape, app path, aggregates | tested (`553`, `562`) |

### `evals/runs/` (repo root)

Committed JSON records, one per run, plus `latest.json`. Baseline: `2026-10-17_eadaef6.json` (EVAL-1, EVAL-2); first four-suite record: `2026-10-17_0a00123.json`.

## Data structures

Record (one file per run; spec 3.4 plus the extra fields marked †):

```
run_id   "<YYYY-MM-DD>_<shortsha>"      commit  "<shortsha>"      date  "<ISO UTC>Z"
seconds† total wall time
config   {backend: "fake", speed: 1.0, tesseract: bool, python†: "3.11.x", tier†: 0}
suites   {"EVAL-1": {title†, tier†, seconds†,
                     examples: [{id, class, score, char_mass_ok†}],
                     skipped†: [{id, class, reason}],
                     aggregate: {mean, min, by_class: {class: mean}}},
          "EVAL-2": {title†, tier†, seconds†,
                     examples: [{id, class, score (= f1), precision, recall, f1}],
                     skipped†: [],
                     aggregate: {mean_f1, min_recall}},
          "EVAL-3": {title, tier, direction†: "lower", seconds,
                     examples: [{id, class, words, checks: {name: {count, rate}},
                                 total_count, total_rate, score (= total_rate)}],
                     aggregate: {mean_rate: {name: rate}, total_mean_rate}},
          "EVAL-4": {title, tier, direction†: "higher", seconds,
                     examples: [{id, class (= category), exact, partial, score (= partial), actual}],
                     aggregate: {accuracy, partial_mean, by_category: {category: accuracy}}}}
```

Compare result: `{baseline, candidate, suites: {id: {aggregate: {key: Δ}, examples: {id: {field: Δ}}}},
regressions: [{suite, id, reason, metrics: {field: {baseline, candidate, delta}}}]}`.

## Spec deviations

1. `latest.json` is a JSON pointer file (`{"run_id", "file"}`), not a symlink (spec 3.4), so it
   survives every checkout and platform.
2. Extra record fields (marked † above): `seconds`, `config.python`, `config.tier`, suite `title`,
   `tier`, `seconds`, `skipped`, and EVAL-1 `char_mass_ok` (the D14 guard kept as data).
3. `--tier` filters only `all`; suites named explicitly run whatever their tier.
4. `report.py` emits markdown only; the HTML scorecard in spec 3.4 is not written yet.
5. `commit` is `HEAD` at run time; uncommitted changes in the working tree are not recorded.
6. (E1) Every suite record carries `direction` (`higher` / `lower`), not in spec 3.4; compare uses
   it, falling back to the registry for records written before E1.
7. (E1) EVAL-3 tolerance is 1.0 for rates and counts alike (spec 3.5 says "1 error for counts");
   a rate is per 1 000 words, so a one-count rise in a long fixture is below the tolerance.
8. (E1) EVAL-3 reports all 12 `run_checks` results (the 11 of the quality docstring plus the
   informational `chapter_number_segments`).
9. (E1) EVAL-4 at tier 0 uses `decide(..., in_lexicon=False)`: misaki's lexicon (rule 4) is not
   loaded (misaki's English module also fails to import here without `num2words`), so the
   heuristic decides where the backend would consult the lexicon; misaki's number reading is not
   modelled either. Spec 3.4 places `data/` under `api/hearnarro/evals/`; the brief's
   `evals/data/` is read as that path.
10. (E1) The dataset is 302 pairs in 14 categories; table and equation pairs set `block` so they go
    through the ING-7 block path rather than plain normalization.

## How to run

From `api/`: `.venv/bin/python -m hearnarro.evals run all` (or `run EVAL-1 EVAL-2`), add
`--baseline <run_id>` to see deltas; `.venv/bin/python -m hearnarro.evals compare <a> <b>`. Gate:
`.venv/bin/python -m pytest tests/test_eval_gate.py`.

## Open items

- EVAL-5..9 suites, `data/listening_rubric.md`, the HTML scorecard (spec 3.3, 3.4).
- EVAL-1 scanned class needs tesseract on this machine (5 fixtures skipped in the baseline).
