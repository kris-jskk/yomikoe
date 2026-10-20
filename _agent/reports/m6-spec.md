TASK        m6-spec
STATUS      done
ASSUMED     - "M6" is the domain-reading milestone as the brief names it; renumbering of the old M6/M7 is left to the parallel task.
            - Datasets live in api/hearnarro/evals/data/ (the M5 Q2 decision applied to the PRD's "evals/data/").
            - Fields and reading settings are stored inside profile_json (no migration); the column alternative is §8 Q6.
            - Per-field SYN-4 overrides are applied as normalize claims so TTSBackend keeps its signature (§8 Q9).
            - All 90 probe lines (850/855/860/865/870/875, 01–15) become fixture lines in api/tests/fixtures/domain_probes.jsonl.

RESULT      1. Spec exists with §0–§8 in the M5 shape; §5a maps all 27 DOM rows to phase, module, test file and EVAL-11 class — done — _agent/results/955_m6_spec_sections.txt (sections; "DOM rows in §5a map: 27")
            2. §3 specifies package api/hearnarro/ingestion/domains/, ten JSON tables under domains/tables/ (7 field + units/elements/currencies) in math_convention.json shape read by tables.py and api/scripts/check_domain_convention.py, claim engine before ING-6 pass one with _speak_symbols last (D49), fields gating via row `fields` vs profile.effective_fields (D45), roles.role_of (D46), units token grammar (D47), segmentation hook via abbreviation_set(fields) (DOM-26) — done — _agent/specs/m6-domain-reading.md §3a–§3g
            3. §1 specifies eval11_domain_speech.py, evals/data/domain_speech.jsonl, mathspeak_score reuse, by_domain/by_class/by_dom/leaks aggregates, eight hygiene steps (decision 28 and more), test_dom_gate.py with its two tests, the 90 probe lines — done — spec §1a–§1d
            4. §7 gives phases 0–6 with rows, 31 briefs (slug, model, budget), evidence ranges 960–1179, exit criteria; §7a assigns D1–D19 (phase 1 fixes all but D9, and parts of D14/D16/D19) — done — spec §7a, §7b; 955 (31 slugs)

OBSERVATIONS
- The TERM-1 academic lexicon and TERM-4 expansion table that DOM-24/25 extend do not exist on this branch (no ACADEMIC/lexicon_academic/EXPANSIONS in api/hearnarro; 956). §8 Q8.
- normalize() already receives a profile on every path (segment.split_sentences, mathspeak prose, renormalize), so the domain pass needs no signature change (956).
- math_convention.json already encodes roles inside key names ("→ (limit or tends)"); the spec adds a `roles` section and keeps those keys.
- The six probe files use three layouts; transcription to fixture lines is by hand.
- docs/PRD_DOMAINS.md changed on disk during the task (the parallel status-wording task); the spec was written from the first read.
- Worker briefs planned: 31.
- Three riskiest rows: DOM-2 (unit vs variable runs in every document: a variable misread as a unit changes all prose); DOM-22 (field detection gates every field rule; misdetection reads `PO`/`CO` wrongly, no accuracy target in the PRD, §8 Q5); DOM-5 (flattened scripts: font-run restoration in merge.py can move goldens and the D14 guard, §8 Q12).

EVIDENCE    _agent/results/955_m6_spec_sections.txt — spec headings §0–§8, 117 DOM- mentions, 7653 words, 27 DOM rows in §5a, 31 brief slugs
            _agent/results/956_m6_spec_code_facts.txt — code names the spec relies on: migrations 0001–0005, no TERM-1/TERM-4 tables, normalize/segment/mathspeak hooks, profile fields, route ProfileIn, suite registry, convention keys, staging dataset counts (278 rows, 15 upper-case spoken, 74 domain/class)

FILES WRITTEN     _agent/specs/m6-domain-reading.md
                  _agent/reports/m6-spec.md
                  _agent/results/955_m6_spec_sections.txt
                  _agent/results/956_m6_spec_code_facts.txt
FILES READ BEYOND THE BRIEF     api/hearnarro/ingestion/abbreviations.py (head), segment.py (grep), profile.py (grep), synthesis/acronyms.py (grep), synthesis/lexicon_overrides.py (head), routes/documents.py (grep), migrations/0005 (grep), mathspeak/markup.py and mathspeak/__init__.py (grep), evals/suites/__init__.py (grep), the six probe files 850–875 (format only)

UNVERIFIED  - That markup_blocks builds a usable `table` block for EVAL-11 (only its signature was read; §1c tells the worker to stop if not).
            - That claim output passes through _speak_symbols unchanged (stated as a design invariant, tested in phase 1, not run).
            - Field detection thresholds and the phase-1 throughput target (< 10 %) are not measured.
NOT DONE    none
DRAFTS      none

OUTPUT      (_agent/results/955_m6_spec_sections.txt)
19:## 0. Scope and gate
54:## 1. Datasets, eval suite, red gate (phase 0)
56:### 1a. EVAL-11 dataset and hygiene (decision 28)
89:### 1b. Class to DOM map (default `dom` per pair)
103:### 1c. EVAL-11 suite
130:### 1d. Probe fixture and gate test (red)
153:## 2. Profile fields and reading settings (phase 0 for DOM-22; phase 5 for DOM-23)
155:### 2a. Model (`api/hearnarro/ingestion/profile.py`, extended)
184:### 2b. Field detection (DOM-22, D45)
201:### 2c. Storage and API
226:### 2d. Web
234:## 3. Domain-reading package and conventions (phases 1–6; DOM-1..21, D46–D49)
236:### 3a. Package `api/hearnarro/ingestion/domains/`
261:### 3b. Claim engine and pass order (D49)
311:### 3c. Units grammar (D47, DOM-1, DOM-2, decisions 4 and 5)
356:### 3d. Convention tables (D48)
394:### 3e. Role-keyed wordings (D46)
418:### 3f. Segmentation hook (DOM-26)
432:### 3g. Mathspeak-side changes
442:## 4. Vocabulary (phase 4; DOM-24, DOM-25)
444:### 4a. Lexicon (DOM-24)
455:### 4b. Abbreviations and acronyms (DOM-25)
465:## 5. Tests (write red first)
490:### 5a. DOM row map
522:## 6. Files and ownership (parallel workers in one phase never share a file)
558:## 7. Phases and evidence
575:### 7a. Cross-domain defects fixed first (phase 1)
599:### 7b. Phases
620:## 8. Open points: supervisor decision needed
DOM- mentions: 117
wc -w:     7653
DOM rows in §5a map: 27
briefs (unique m6-p slugs):       31
