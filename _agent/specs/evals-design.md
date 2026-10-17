# HearNarro evals: what they are, why this project needs them, and the design

Status: proposed design, 2026-10-17. Nothing here is implemented. Facts about the current
code come from `_agent/results/531_eval_recon.md` (read-only recon, cited there by file:line).
Decisions below are numbered D31–D34 and are **proposed**, not decided; they go into
`docs/TECHNICAL_DESIGN.md` only when the user accepts them.

## 1. What an eval is (plain words)

A **test** asks a yes/no question about one behaviour: "does the light switch turn the light
on?" It passes or fails, and it is run on every change to stop breakage.

An **eval** (evaluation) asks "how good is it, and compared with what?" It runs the system over
a fixed set of examples (a *dataset*), applies a *scorer* to each example, keeps every
per-example score, aggregates them (mean, worst case, distribution), and stores the result next
to the commit that produced it so two runs can be compared. An eval does not fail by itself;
it produces numbers and a diff. A *gate* is an eval with a threshold bolted on.

Three ideas carry everything:

| Idea | Meaning | HearNarro example |
|---|---|---|
| Dataset | fixed inputs with known-good answers (ground truth) | 20 fixture PDFs + hand-corrected `expected.jsonl` |
| Scorer | a function from (system output, ground truth) to a number | word-sequence edit-distance score, 0..1 |
| Record | the scores, saved with commit id, date and config | today: printed to the terminal and lost |

## 2. Why HearNarro needs evals (the gaps the recon found)

1. **Scores exist but are thrown away.** Reading order (word score per PDF), sentence
   boundaries (precision/recall/F1 per fixture), the 11-check quality checklist, time-stretch
   accuracy, time-to-first-audio, real-time factor and highlight drift are all computed
   today, then reduced to pass/fail against a threshold. Nobody can answer "did the parser
   get better or worse on the two-column papers after the ligature fix?" except by reading
   old transcripts. The last recorded reading-order mean is 0.9914 (`docs/M1_TESTING.md`,
   not re-run); nothing tracks it.
2. **Silent regressions inside the threshold.** A per-PDF floor of 0.95 means a fixture can
   drift from 0.99 to 0.96 without any test noticing. For a listener that is several
   misplaced sentences per document.
3. **The speech layer has no quality metric at all.** Normalization (numbers, units,
   abbreviations), acronym decisions and pronunciation are checked by hand-written
   examples that assert a boolean. There is no accuracy figure over a corpus and no record
   of what the model actually says.
4. **Audio and timestamps are measured only against the fake backend.** `FakeBackend`
   emits silence with perfect timestamps, so every synthesis test proves plumbing, not
   speech. No check compares Kokoro's word timestamps to the audio; highlight drift on real
   audio is a manual check in the PRD.
5. **Backend swaps are a stated goal with no measuring stick.** `TTSBackend` exists so the
   model can change; without an eval there is no way to say a new backend is better, faster
   or more intelligible than Kokoro on the same sentences.
6. **OCR accuracy is untested by design**, and the 5 scanned fixtures are skipped where
   tesseract is absent. When it is installed, nothing will say how good it is.

## 3. Design

### 3.1 Principle (D31, proposed): an eval is a scored test with the threshold removed and the per-example score kept

The existing scorers (`api/tests/golden_util.py`, `api/tests/boundary_util.py`,
`api/hearnarro/quality.py`, `api/scripts/bench.py`) are reused as-is. The eval layer adds
three things only: a **runner** that calls them over the datasets and keeps every score, a
**store** of run records, and a **compare/report** step. Gate tests keep their thresholds and
stay the CI floor; evals are the trend line above the floor.

### 3.2 The eval loop

```
 dataset ──► system under test ──► output ──► scorer ──► per-example scores
 (fixed)      (ingest / synth /                           │
               player, at a      ◄─── config ───┐          ▼
               given commit)                    │     run record (JSON)
                                                │     commit, date, config,
                                                │     per-example, aggregates
                                                │          │
                                       compare with baseline run
                                                │
                                                ▼
                                   scorecard: mean, worst, Δ per example,
                                   regressions flagged (Δ < -0.01 or new failure)
```

### 3.3 Suites

Each suite = dataset + scorer + aggregate + cost tier. IDs are `EVAL-n` (new family;
requirement IDs ING/SYN/PLAY/LIB are untouched).

| Suite | Question it answers | Dataset | Scorer | Aggregates | Tier | Status of parts |
|---|---|---|---|---|---|---|
| EVAL-1 Order | Is the prose in the right order? (ING-3/4/5) | 20 fixture PDFs, `*.expected.jsonl` | `golden_util.word_score` (1 − edit distance / expected words); char-mass guard | mean, min, per class (academic / report / scanned / tables) | 0 fast | scorer exists; runner new |
| EVAL-2 Boundaries | Are sentences split where a reader would pause? (ING-5, SYN-1) | 15 `*.sentences.txt` | `boundary_util.prf` → precision, recall, F1 | mean F1, min recall | 0 | scorer exists |
| EVAL-3 Clean text | How much junk reaches the voice? (ING-1..6) | same 15 fixtures | `quality.run_checks` counts, normalized per 1 000 words | per-check rate, total | 0 | checks exist; rate normalization new |
| EVAL-4 Speech form | Does the text we send to the voice read aloud correctly? (ING-6, ING-7, SYN-4) | **new**: `evals/data/speech_form.jsonl`, ~300 pairs (raw text → expected spoken text) covering numbers, dates, units, ordinals, abbreviations, acronyms (spell vs say), tables cues, equations | exact match on the spoken string; word-level edit distance as partial credit | accuracy, per-category accuracy | 0 | dataset and scorer new |
| EVAL-5 Intelligibility | Can the audio be understood? (SYN-1, SYN-4) | 50 fixture sentences (`sample_sentences.py` already picks them) | round trip: Kokoro → ASR (an MIT-licensed Whisper build) → word error rate vs the normalized input | WER mean, worst sentence, per voice | 1 model | new; needs the ASR dependency and licence check |
| EVAL-6 Sync | Do the word timestamps match the audio? (SYN-1, PLAY-3) | same 50 sentences | ASR word timings vs backend timestamps: mean absolute offset in ms, share of words within 150 ms | mean offset, p95, per speed 0.5/1/2/3x | 1 | new |
| EVAL-7 Speed | How fast is synthesis on this machine? (SYN-5, PRD metrics) | 20 bench sentences | `bench.py` TTFA and real-time factor | p50/p95 TTFA, RTF | 1 | exists as a script; fold output into the record format |
| EVAL-8 OCR | How accurate is the scanned path? (ING-2) | 5 scanned fixtures | character error rate vs expected text | CER mean, max | 1 (tesseract) | new; blocked until tesseract installed |
| EVAL-9 Listening | Does it sound good to a person? | 10 sentences × 2 voices | a 1–5 rubric sheet (naturalness, pronunciation errors counted, pacing) filled by a human | mean per voice, error count | 2 human | new; a markdown form the runner ingests |

Tier 0 runs in seconds with no model and belongs in every eval run. Tier 1 needs Kokoro on
CPU (minutes) and runs on demand or nightly. Tier 2 is a scheduled human session, recorded
in the same store so it sits next to the machine scores.

### 3.4 Layout (D32, proposed)

```
api/evals/
  __init__.py
  runner.py          run <suite|all> [--tier 0|1] [--baseline <run-id>] → writes a run record
  suites/            one module per EVAL-n; each exposes dataset(), score(example, output), aggregate(scores)
  data/              speech_form.jsonl, listening_rubric.md; PDFs stay in api/tests/fixtures
  store.py           evals/runs/<date>_<shortsha>.json; latest.json symlink; compare(a, b)
  report.py          markdown scorecard (for the terminal and the PR body) and an HTML scorecard
evals/runs/          committed JSON records, one per run (small; per-example scores only)
```

Record shape (one file per run):

```json
{"run_id":"2026-10-17_7f2f015","commit":"7f2f015","date":"2026-10-17T14:02:00Z",
 "config":{"backend":"fake","speed":1.0,"tesseract":false},
 "suites":{"EVAL-1":{"examples":[{"id":"arxiv_2401_01234","class":"academic","score":0.993}],
                      "aggregate":{"mean":0.991,"min":0.962,"by_class":{"academic":0.988}}}}}
```

### 3.5 Compare and regressions (D33, proposed)

`compare(baseline, candidate)` reports, per suite, the aggregate deltas and every example whose
score fell by more than a suite-specific tolerance (0.01 for scores in 0..1, 10 % for timing,
1 error for counts). A regression is a report line, not a test failure. The gate tests remain
the only thing that blocks a merge; a CLAUDE.md rule can later require "no unexplained eval
regression" in a PR description once the suites have a baseline.

### 3.6 Where evals run

- Developer: `api/.venv/bin/python -m evals run all --tier 0` before and after a parser or
  normalizer change; `--tier 1` when touching synthesis or swapping a backend.
- Milestone close: full tier 0 + 1 run recorded and linked from the milestone guide.
- Backend swap (the TTSBackend promise): EVAL-5/6/7 run once per backend with identical
  sentences, voices mapped by gender/accent; the scorecard is the decision document.

### 3.7 What evals will not do here (D34, proposed)

No LLM-as-judge in v1: every scorer is deterministic or a human rubric, so a score is
reproducible and the licence rule stays simple. No per-user telemetry: datasets are the
fixtures and committed sentence lists, never a user's uploads.

## 4. Rollout (milestone-style, gate first)

| Phase | Deliverable | Acceptance |
|---|---|---|
| E0 Runner + store | `api/evals/runner.py`, `store.py`, EVAL-1 and EVAL-2 wrapped | one run record written; `compare` of two identical runs shows zero deltas |
| E1 Fast suites | EVAL-3, EVAL-4 with its ~300-pair dataset | tier 0 completes under 60 s; per-category accuracy printed |
| E2 Model suites | EVAL-5, EVAL-6, EVAL-7 under `HEARNARRO_TEST_MODEL=1`; ASR dependency through the licence check | one tier-1 record on this machine; WER and sync offset reported per speed |
| E3 Reporting | markdown + HTML scorecard; baseline rule in CLAUDE.md | scorecard linked from a milestone guide |
| E4 Human + OCR | EVAL-9 rubric and ingestion; EVAL-8 once tesseract is present | one listening session recorded |

## 5. Open questions for the user

1. Accept the `EVAL-n` id family and D31–D34 as proposed, or fold evals into the existing
   requirement families?
2. Is adding an ASR dependency (Whisper, MIT) for EVAL-5/6 acceptable as a dev-only
   dependency (not shipped), or should audio evals stay human-only for now?
3. Should eval run records be committed to the repo (`evals/runs/`), or kept out of git?
