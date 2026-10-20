# HearNarro M5 code map: academic reading

This document explains how the M5 additions work end to end and what every file M5 added or changed
does. It is written for an engineer who has read `docs/PRD.md` (what), `docs/TECHNICAL_DESIGN.md`
(how; D36–D40) and `docs/CODE_MAP_M4.md` (the library and ingestion flows this map extends).

The design the code is built against is `_agent/specs/m5-academic-reading.md` (the spec). Where the
code and the spec differ, this map says what the code does and lists the difference under
"Spec deviations".

## Scope and status

Updated 2026-10-17 on branch `m5-academic`, phase 2 (ING-11 document profile). Later phases
(mathspeak MATH-1..4, code listings ING-10, lexicon TERM-1..4, player PLAY-10/11) add their flows
and rows here when they land.

### Status words

| Word | Meaning |
| --- | --- |
| implemented | Real code; exercised only indirectly or by hand. |
| tested | Real code plus a passing saved run that exercises it. |
| planned | In the spec, not built yet. |

## Code flows

### a. Profile at ingestion (ING-11, D40)

1. `storage/jobs.run_ingestion` calls `ingestion.pipeline.ingest(pdf)`.
2. `ingest()` runs stages 1–4 as in M4: `extract_pages` (+ `apply_ocr`), `classify_pages`,
   `order_document`, `merge_blocks`.
3. **Between stage 4 and stage 5**, `profile.compute_profile(pages, blocks)` measures the merged
   blocks: maths mass (equation `raw_text` plus inline maths), display equations per page (a run of
   consecutive `equation` blocks counts once), the share of prose tokens carrying a maths glyph,
   code share (monospace glyph share of the text layer until ING-10 `code` blocks exist), citation
   style (numeric brackets vs author–year, ≥ 3 wins) and scanned-page share; `classify` gives
   `prose`, `mixed` or `math`.
4. Stage 5: `segment.split_sentences(block, ..., profile=profile)` passes it to
   `normalize.normalize(text, heading=..., profile=..., math_spans=...)`. Bracket rule: `prose`
   drops every numeric bracket group (M4 behaviour, the default); `math`/`mixed` copy a group that
   lies inside a maths span (interval, matrix) and drop only citation-shaped groups outside maths.
   Maths spans arrive with MATH-2 (phase 3); until then no span is passed, so output is unchanged.
5. `IngestResult.profile` is written by `jobs._write_result` as `documents.profile_json`
   (`DocumentProfile.to_json`).

### b. Profile in the API and the library badge (ING-11, LIB-1)

1. `GET /documents` and `GET /documents/{id}`: `routes/documents._document_summary` adds
   `profile` = `{class, computed_class, override, math_share, display_per_page,
   inline_token_share, code_share, citation_style, scanned_share, author_year_citations}` from
   `repo.document_profile(row)`; a NULL `profile_json` (ingested before migration 0005) reads as
   `PROSE_DEFAULT`.
2. `web/src/components/Library.tsx` `ProfileBadge` shows `formatProfile(doc.profile)`
   (`data-testid="doc-profile"`): the effective class, "(auto)" when not overridden.

### c. Override and re-normalize (ING-11, D40)

1. Clicking the badge opens a select (auto / prose / mixed / math); a choice sends
   `PATCH /documents/{id}` with `{profile: {class}}` (`class: null` clears the override).
2. The route returns 409 while `status == 'parsing'`, 422 for an unknown class, then runs
   `_apply_profile` in `asyncio.to_thread` on a sync connection: `repo.set_profile_override`
   stores the new profile; if it changed, `cli.renormalize_document` re-runs `normalize` with the
   stored profile over every segment (the `hearnarro renormalize` path, no re-ingest) and deletes
   the changed segments' `audio_cache` rows.
3. The response is the summary plus `renormalized: {changed, removed}`; the badge shows
   "re-normalized N sentences" (`formatRenormalized`).

## Modules and files

| File | Responsibility | Public (M5 additions) | Reads / writes | Status |
| --- | --- | --- | --- | --- |
| `api/hearnarro/ingestion/profile.py` (new) | Document profile and class (ING-11, D40); inline maths mass = max(non-display `MathSpan` chars, maths-glyph token chars), display spans not counted twice, OCR pages keep the token estimate (m5-p3c) | `DocumentProfile` (`effective`, `with_override`, `to_json`, `from_json`), `PROSE_DEFAULT`, `compute_profile`, `classify`, `citation_style`, threshold constants | pages, merged blocks; pure | tested (`test_ing11_profile.py`, gate e 682, 713: 28/30) |
| `api/hearnarro/ingestion/pipeline.py` | Calls `compute_profile` between `merge_blocks` and `split_sentences`; `IngestResult.profile`; calls `apply_mathspeak(segments, blocks, pages, profile)` after the `split_sentences` loop (MATH-1..4, spec §2b) | `ingest`, `IngestResult` | — | tested (682, 686, 713, 714, 716) |
| `api/hearnarro/ingestion/segment.py` | `split_sentences(..., profile=)` forwards the profile to `normalize` | `split_sentences` | — | tested (686) |
| `api/hearnarro/ingestion/mathspeak/__init__.py` (new) | The step after stage 5 (MATH-1..4, D36): `speak_segment` pure core; `apply_mathspeak` clips block spans to segments, adds `glyph_spans` (text-font maths tokens with a MATH-3-named non-ASCII glyph, units and references left to their rewrites) and fills `Segment.math_json` (set as an attribute; `models.Segment` has no field) | `apply_mathspeak`, `speak_segment`, `speak_span`, `glyph_spans`, `math_segments`, `char_map_errors` | segments in place | tested (`test_mathspeak_*.py` 703, gate b 714) |
| `api/hearnarro/ingestion/mathspeak/structure.py` (new) | `Node` tree from span geometry; labels at either end of a display; CMEX code points (control-char delimiters, `P`/`Q`/`R`/`p` operators and radicals) read as the glyphs they draw; script detection against the largest non-CMEX size | `Node`, `parse`, `label_of`, `cmex_text`, `LIMOPS`, `RELATIONS` | — | tested (703, 716) |
| `api/hearnarro/ingestion/mathspeak/reader.py` (new) | §3c English for a tree; `fallback` = "equation N" + symbol names for a display, symbol names only for an inline span; digit runs and function names read whole | `speak`, `fallback`, `prefix` | — | tested (703, `test_eval_gate.py` 716) |
| `api/hearnarro/ingestion/mathspeak/symbols.py` (new) | MATH-3 table from `api/scripts/math_convention.json`; mathematical alphanumerics (𝑥) named as their plain letter; units, SI prefixes, chemical formulas | `SYMBOLS`, `GREEK`, `FUNCTIONS`, `ACCENTS`, `name_of`, `rewrite_units` | reads the convention JSON | tested (703) |
| `api/hearnarro/ingestion/mathspeak/references.py`, `markup.py` (new) | MATH-4 reference rewrites and theorem openers; the `math_speech.jsonl` markup to span geometry helper | `rewrite_references`; `markup_runs`, span builders | — | tested (703, 701) |
| `api/hearnarro/ingestion/normalize.py` | `normalize(..., profile=, math_spans=)`; bracket rule by class (a group starting with 0 is an interval under every profile, ING-6); `_speak_symbols` runs as the second pass at the end, on prose only (mathspeak inserts spoken maths afterwards) | `normalize` | — | tested (`test_ing11_profile.py`, `test_math1_symbol_fallback.py`) |
| `api/hearnarro/ingestion/math_symbols.py` (from main, merge `79e945a`) | MATH-1 symbol fallback: 76 symbols plus Greek letters by name, used by the `_speak_symbols` second pass in `normalize` | symbol table | — | tested (`test_math1_symbol_fallback.py`) |
| `api/hearnarro/storage/migrations/versions/0005_profile_math.py` (new) | `documents.profile_json`, `segments.math_json` (phase 3 writes it) | revision `0005` | schema | tested (684, `test_ing11_profile_api.py`) |
| `api/hearnarro/storage/jobs.py` | Writes `profile_json` with the ingest result; writes `segments.math_json` (JSON of the `math_json` entries `apply_mathspeak` set, NULL otherwise) | `_write_result`, `_math_json` | `documents`, `segments` | tested (686, `test_syn1_renormalize_cli.py` 716) |
| `api/hearnarro/storage/repo.py` | `profile_json` in `DOCUMENT_COLUMNS`; profile read and override | `document_profile`, `get_document_profile`, `set_profile_override` | `documents` | tested (`test_ing11_profile_api.py`) |
| `api/hearnarro/routes/documents.py` | Summary `profile`; PATCH `profile` with re-normalize, 409, 422 | `ProfileIn`, `DocumentPatch.profile`, `_profile_summary`, `_apply_profile` | `documents`, `segments`, `audio_cache` | tested (`test_ing11_profile_api.py`) |
| `api/hearnarro/cli.py` | `renormalize_document` reads the stored profile; a segment with `math_json` (or a unit or equation reference) is re-spoken by `speak_segment` from its stored spans, the rest go through `normalize`, as at ingestion | `renormalize_document` | `segments`, `audio_cache` | tested (`test_syn1_renormalize_cli.py`, API test) |
| `web/src/api/types.ts` | `DocumentProfile`, `ProfileClass`, `DocumentSummary.profile`/`renormalized`, `DocumentPatch.profile` | types | — | implemented (build 683) |
| `web/src/components/Library.tsx` | Profile column and `ProfileBadge` select | `Library` | `PATCH /documents/{id}` | implemented (build 683; no e2e run) |
| `web/src/components/libraryFormat.ts` | `formatProfile`, `formatRenormalized` | helpers | — | tested (`library.test.ts`, 683) |
| `api/tests/test_ing11_profile.py`, `api/tests/test_ing11_profile_api.py` (new) | Unit and API tests for the above | — | tmp data dirs | fixture |

## Spec deviations

- Thresholds tuned on the fixtures (D40 allows it): D40's first thresholds matched 17 of 30
  (`_agent/results/677_profile_stats_d40_thresholds.txt`), the tuned ones 28 of 30
  (`681_profile_stats_tuned.txt`). See `profile.py`'s module docstring.
- `DocumentProfile` gains `inline_token_share` (default 0.0, so older JSON still loads); the
  summary also carries `display_per_page` and `inline_token_share`.
- Inline maths mass is estimated from maths-glyph tokens until `LogicalBlock.math_spans` exists
  (phase 3), and code share from monospace glyphs until `code` blocks exist (ING-10).
- `renormalize_document` does not yet read `segments.math_json` (phase 3 defines its format).
- `web/tests/e2e/profile.spec.ts` is not written in phase 2.
