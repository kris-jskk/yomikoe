# HearNarro M5 code map: academic reading

This document explains how the M5 additions work end to end and what every file M5 added or changed
does. It is written for an engineer who has read `docs/PRD.md` (what), `docs/TECHNICAL_DESIGN.md`
(how; D36–D40) and `docs/CODE_MAP_M4.md` (the library and ingestion flows this map extends).

The design the code is built against is `_agent/specs/m5-academic-reading.md` (the spec). Where the
code and the spec differ, this map says what the code does and lists the difference under
"Spec deviations".

## Scope and status

Updated 2026-10-20 on branch `m5-academic`, phase 4 (vocabulary, TERM-1..4; built 2026-10-20,
phase 4, merged tree `eac6c2c`, summary `_agent/results/1091_phase4_summary.md`). Phase 2 added
flows a–c, phase 3 the mathspeak rows, phase 4 flows d–e and the TERM rows. The player additions
(PLAY-10/11, SYN-8 pauses, MATH-5) add theirs in phase 5.

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

### d. Pronunciation override (TERM-2; built 2026-10-20, phase 4)

1. In the reader a word selection opens `PronounceDialog` (`pickWord` takes the selected word); the
   user types a respelling and picks "this document" or "all documents". `submitPronunciation` calls
   `client.putPronunciation` with `{document_id, word, respelling}` (`document_id: null` for global).
2. `PUT /pronunciations` (`routes/pronunciations.py`): 422 for an empty word or a respelling with no
   letter, 404 for an unknown document; `repo.put_pronunciation` upserts the row in `pronunciations`
   (migration 0006; `word` stored lower case; a partial unique index covers the global rows, whose
   `document_id` is NULL).
3. `_after_change` runs `_invalidate` in a thread: `segments_with_word` finds every segment of the
   document (or of all documents for a global change) whose `normalized_text` holds the word as a whole
   token, case-insensitive; `cli.purge_segments` deletes those segments' `audio_cache` rows and files and
   returns the count. SYN-6 keys are unchanged (still by segment id).
4. `SynthesisService.invalidate_context(document_id | None)` drops the cached `SynthContext` (all of them
   for a global change). The response is the row plus `invalidated`; `DELETE /pronunciations/{id}`
   follows the same steps and returns `{invalidated}`.
5. Web: `onPronounceSaved` calls `usePlayer.dropClips(segmentsWithWord(segments, word))`, which aborts
   pending and scheduled clips of those segments and rebuilds through SEEK or PLAY, so the next play
   refetches (D5, D10). Listen (after a save) is `usePlayer.listen` → `seekTo` → machine PLAY (idle or
   error) or SEEK.
6. Next synthesis: `_context` reloads acronyms and `DbSegmentRepo.document_lexicon`
   (= `repo.pronunciations_for`, global merged under per-document) into `SynthContext.lexicon`;
   `KokoroBackend` turns each respelling into phonemes once per (accent, lexicon) with
   `respelling_phonemes(g2p, lexicon)` and applies them through `lexicon_overrides.apply(tokens,
   extra=...)`. Precedence: user respelling > `lexicon_overrides.OVERRIDES` > `lexicon_academic`
   (TERM-1) > the backend's gold lexicon.

Evidence: route and purge tests 6 passed (`_agent/results/1021_term2_green.txt`), route bodies
(`1026_routes.md`), web unit tests 12/12 (`1061_vitest_green.txt`), e2e in three engines
(`1067_e2e_three_engines.txt`), control run with `dropClips` disabled failing the refetch assertion
(`1060_red.txt`).

### e. Citations and abbreviations in the normalizer (TERM-3, TERM-4; built 2026-10-20, phase 4)

1. Stage 5 `normalize.normalize(text, profile=..., math_spans=...)` keeps its one-pass `_PATTERN`;
   phase 4 adds two named groups, `authyear` and `expand`, emitted by the same `emit` mechanism.
2. `authyear` (TERM-3): an author–year parenthetical such as "(Smith et al., 2019)" becomes
   "Smith et al 2019" when `profile.author_year_citations == "read"` (the default) and is dropped when
   `"skip"`; a semicolon list is read in turn and "&" becomes "and"; a group inside a maths span is
   left to the maths rule; numeric clusters stay dropped (ING-6). The toggle is the document setting
   `PATCH /documents/{id}` `profile.author_year_citations`, which re-normalizes (spec Q6).
3. `expand` (TERM-4): a whole token from `ingestion/expansions.EXPANSIONS` (12 entries, spec §4c
   wordings), any case, becomes its expansion, capitalised at a sentence start; `char_map` maps the
   expansion back to the abbreviation's characters.
4. Sentence splitting is separate: `abbreviations.LATIN` gains "w.r.t.", "s.t.", "w.l.o.g.", "op.",
   "cit." so the splitter does not cut after them (they are non-terminal tokens, not expansions).

Evidence: math_chem rows checked against the convention (`_agent/results/1042_math_chem_check.md`),
EVAL-4 categories (`1045_eval4_categories.md`, `term_abbreviation` 0.00 → 0.90), suite
(`1046_suite.txt`).

## Modules and files

| File | Responsibility | Public (M5 additions) | Reads / writes | Status |
| --- | --- | --- | --- | --- |
| `api/hearnarro/ingestion/profile.py` (new) | Document profile and class (ING-11, D40); inline maths mass = max(non-display `MathSpan` chars, maths-glyph token chars), display spans not counted twice, OCR pages keep the token estimate (m5-p3c) | `DocumentProfile` (`effective`, `with_override`, `to_json`, `from_json`), `PROSE_DEFAULT`, `compute_profile`, `classify`, `citation_style`, threshold constants | pages, merged blocks; pure | tested (`test_ing11_profile.py`, gate e 682, 713: 28/30) |
| `api/hearnarro/ingestion/merge.py` | Stage 4; MATH-2 inline spans: maths-font runs, content spans (p3d), and (m5-p3i) a lone italic or calligraphic-slant letter in upright prose (`_italic_variables`), which yields to an overlapping content span and is read from its text when an accent glyph follows (m5-p3k) A list item made of whole lines (`_item_lines`) keeps its maths-font inline spans (`_inline_spans` over its own lines); a line split before an inline glyph item still carries none. | `merge_blocks`, `content_spans`, `_math_runs`, `_italic_variables` | stage 3 blocks; pure | tested (`test_mathspeak_loop5.py`, gate b 822) |
| `api/hearnarro/ingestion/pipeline.py` | Calls `compute_profile` between `merge_blocks` and `split_sentences`; `IngestResult.profile`; calls `apply_mathspeak(segments, blocks, pages, profile)` after the `split_sentences` loop (MATH-1..4, spec §2b) | `ingest`, `IngestResult` | — | tested (682, 686, 713, 714, 716) |
| `api/hearnarro/ingestion/segment.py` | `split_sentences(..., profile=)` forwards the profile to `normalize` | `split_sentences` | — | tested (686) |
| `api/hearnarro/ingestion/mathspeak/__init__.py` (new) | The step after stage 5 (MATH-1..4, D36): `speak_segment` pure core; `apply_mathspeak` clips block spans to segments, adds `glyph_spans` (text-font maths tokens with a MATH-3-named non-ASCII glyph or a U+2044 drawn-fraction slash, units and references left to their rewrites) and fills `Segment.math_json` (set as an attribute; `models.Segment` has no field) (m5-p3k) `_maths_gap` accepts a text-font function word with its bracket (" sin("), the gap run takes the larger part's size; `_grow` joins a text-font limit operator (`LIMOPS`) before a span that opens with a script ("lim" + "x→0"). | `apply_mathspeak`, `speak_segment`, `speak_span`, `glyph_spans`, `math_segments`, `char_map_errors` | segments in place | tested (`test_mathspeak_*.py` 703, gate b 714) |
| `api/hearnarro/ingestion/mathspeak/structure.py` (new) | `Node` tree from span geometry; labels at either end of a display; CMEX code points (control-char delimiters, `P`/`Q`/`R`/`p` operators and radicals) read as the glyphs they draw; script detection against the largest non-CMEX size; `(a)⁄(b)` (U+2044, from `extract.vector_maths`) is a `frac`; a three-level display's fraction ends at its bar's right edge, a relation set in the numerator run stays on the main row, and stacked limits follow their CMEX operator (m5-p3j, 832) (m5-p3k) `_lex` folds mathematical alphanumerics (U+1D400..1D7FF, unicode-math text layers) to plain letters, so 𝑙𝑜𝑔 is the function word log. | `Node`, `parse`, `label_of`, `cmex_text`, `LIMOPS`, `RELATIONS` | — | tested (703, 716) |
| `api/hearnarro/ingestion/mathspeak/reader.py` (new) | §3c English for a tree; `fallback` = "equation N" + symbol names for a display, symbol names only for an inline span; digit runs and function names read whole; `√(…)` drops the delimiting brackets (m5-p3j) | `speak`, `fallback`, `prefix` | — | tested (703, `test_eval_gate.py` 716) |
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
| `api/hearnarro/synthesis/lexicon_academic.py` (new, m5-p4a; built 2026-10-20, phase 4) | TERM-1 academic lexicon, data written by the project: domain → lower-case word → US phonemes, 38 entries at `eac6c2c` (math 6, stats 6, physics 3, chem 1, bio 2, cs 4, latin_greek 1, surname 15; 37 at m5-p4a, json/gui/anova added by m5-p4e) | `ACADEMIC`, `flat` | pure | tested (`1003_term_by_category.md`, counts `1105_lexicon_counts.txt`) |
| `api/hearnarro/synthesis/lexicon_overrides.py` | SYN-4 hand overrides; `extra` carries a document's respelling phonemes (TERM-2), consulted before `OVERRIDES` | `OVERRIDES`, `lookup(token, extra=None)`, `apply(tokens, extra=None)` | pure | tested (`1006_suite.txt`) |
| `api/hearnarro/synthesis/kokoro_backend.py` | `build_g2p` writes `lexicon_academic.flat()` then `OVERRIDES` into the gold lexicon, lower-case and capitalised keys (misaki keeps proper nouns of 7 letters or fewer capitalised); `respelling_phonemes` turns `SynthContext.lexicon` into phonemes once per (accent, lexicon) | `build_g2p`, `respelling_phonemes(g2p, lexicon)`, `KokoroBackend` | — | tested (`1006_suite.txt`, `1008_model_tests.txt`) |
| `api/hearnarro/synthesis/service.py` | `_context` loads acronyms and the user lexicon (a document with overrides but no acronyms gets a context); `invalidate_context` drops one or all cached contexts; `DbSegmentRepo.document_lexicon` wraps `repo.pronunciations_for` | `SynthesisService._context`, `SynthesisService.invalidate_context(document_id \| None)`, `DbSegmentRepo.document_lexicon` | `pronunciations` (read) | tested (`1021_term2_green.txt`) |
| `api/hearnarro/storage/migrations/versions/0006_pronunciations.py` (new, m5-p4b) | Table `pronunciations` (NULL `document_id` = global), partial unique index for the global scope | revision `0006` (down `0005`) | schema | tested (`1021_term2_green.txt`) |
| `api/hearnarro/storage/repo.py` | TERM-2 rows: list, get, upsert, delete; `pronunciations_for` merges global under per-document | `list_pronunciations`, `get_pronunciation`, `put_pronunciation`, `delete_pronunciation`, `pronunciations_for` | `pronunciations` | tested (`1021_term2_green.txt`) |
| `api/hearnarro/routes/pronunciations.py` (new, m5-p4b) | `GET`/`PUT`/`DELETE /pronunciations`; 422 empty word or respelling without a letter, 404 unknown document or id; purge of the affected segments and context drop on every change, count returned as `invalidated` | `list_pronunciations`, `put_pronunciation`, `delete_pronunciation`, `segments_with_word` | `pronunciations`, `segments`, `audio_cache` and audio files | tested (`1021_term2_green.txt`, bodies `1026_routes.md`) |
| `api/hearnarro/cli.py` | `purge_segments` shares `_purge_where` with `purge_audio` | `purge_segments(conn, segment_ids, data_dir) -> int` | `audio_cache`, audio files | tested (`1021_term2_green.txt`) |
| `api/hearnarro/ingestion/normalize.py` (m5-p4c) | Named groups `authyear` (TERM-3, by `profile.author_year_citations`) and `expand` (TERM-4) in the one-pass `_PATTERN` | `normalize` | — | tested (`1045_eval4_categories.md`, `1046_suite.txt`) |
| `api/hearnarro/ingestion/expansions.py` (new, m5-p4c) | TERM-4 table, 12 entries; "configurable" in the PRD means this one table in M5 | `EXPANSIONS` | pure | tested (`1045_eval4_categories.md`) |
| `api/hearnarro/ingestion/abbreviations.py` (m5-p4e) | `LATIN` gains w.r.t., s.t., w.l.o.g., op., cit. (non-terminal for the sentence splitter only) | `LATIN` | — | tested (`1089_suite.txt`) |
| `api/hearnarro/evals/suites/eval4_speech_form.py` (m5-p4e) | Spec Q8: `score` = `joined` for every `term_*` category, `partial` elsewhere; `partial` and `exact` kept in the record | `joined_similarity`, `score`, `phonemes` | `evals/data/speech_form.jsonl` | tested (`1081_scorer_green.txt`, `1088_eval4_categories.md`, example `1104_koh_shee_example.txt`) |
| `web/src/components/PronounceDialog.tsx` (new, m5-p4d) | TERM-2 dialog: word, respelling, this document / all documents, Save, Listen after a save, the server's 422 message shown | `PronounceDialog`, `submitPronunciation`, `pickWord`, `segmentsWithWord`, `PronounceScope` | `PUT /pronunciations` | tested (`1061_vitest_green.txt`, `1067_e2e_three_engines.txt`) |
| `web/src/player/usePlayer.ts` (m5-p4d) | `dropClips` aborts pending and scheduled clips of the given segments and rebuilds through SEEK or PLAY; `listen` = `seekTo` (D5, D10) | `dropClips(segmentIds)`, `listen(segmentId)` | — | tested (`1067_e2e_three_engines.txt`, control `1060_red.txt`) |
| `web/src/api/client.ts` (m5-p4d) | TERM-2 calls | `listPronunciations`, `putPronunciation`, `deletePronunciation` | `/pronunciations` | tested (`1061_vitest_green.txt`) |

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


**m5-p3j (2026-10-20):** `api/hearnarro/ingestion/extract.py` gains `vector_maths` (pure) and `_strokes`, called in `extract_pages` before `group_lines`: drawn fraction bars and radicals over text-font glyphs (word-processor PDFs) become one linear run `√(…)` / `(num)⁄(den)` with Unicode scripts and `∑`; TeX maths fonts, frames (vertical edges, >80 glyphs) and table rules (upright prose parts, text continuing the row) are left alone. Status: tested (`test_mathspeak_loop6.py`, goldens 834, gate b 832).

**m5-p3n (2026-10-20):** `extract._line_from_layout` splits a same-font run where a glyph's top and bottom both move half a size (`_level_jump`), so a display's numerator and main row are separate spans. `mathspeak/structure.py`: the main row of a three-level display is the first full-size run holding a relation (a display may open with a fraction); `˙` and `¨` are pre-accents (dot, double dot); variation selectors are dropped; runs inside a tall bracket pair `[︂ … ]︂` become a `stack` token (`_stack_tok`: lines by top, cells by gap, script-size centred line pairs as fractions) parsed as `colvec` (one column) or `matrix`. `mathspeak/reader.py` reads `colvec` as "the column vector a, b" (§3c row added). `merge._inline_spans`: a spacing accent ending the text run before a maths run opens the maths span ("˙𝑧" is "z dot"). Tests: `api/tests/test_mathspeak_loop8.py` (tested).

**m5-p3o (2026-10-20):** `mathspeak/reader.py`: a stacked fraction whose numerator and denominator are both Leibniz parts (`_leibniz_part`: d, ∂ or dⁿ followed by one symbol with optional scripts or accent) reads "d y over d t" with no wrapper (§3c "Leibniz derivative" row, also in `api/scripts/math_convention.json`). `mathspeak/__init__.py`: `_maths_gap` accepts a text-font sign with its number ("+2" between "¨𝑦" and "𝜁𝜔0"). Tests: `api/tests/test_mathspeak_loop9.py` (tested); two loop-8 assertions follow the new row.

**Phase 4 (built 2026-10-20):** the spec's repo function `pronunciations_for` exists in `storage/repo.py`;
the service reads it through `DbSegmentRepo.document_lexicon` (`synthesis/service.py`), the same adapter
pattern as `document_acronyms`. A synthesis job already in flight when a `PUT` lands can still write a
clip with the old lexicon (m5-p4b observation, untested). The narrative form "Smith et al. (2019)" is not
matched by `authyear` (m5-p4c observation). No listening check of the lexicon entries or respellings was
run; pronunciation judgments are from dictionary knowledge until tier 1 at close.
