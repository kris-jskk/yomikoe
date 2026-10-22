TASK        domain-speech-chemistry
STATUS      done
ASSUMED     Where the classroom reading and spec §3c differ, the note picks one wording and lists the conflict as an open question (K subscripts "k s p", configurations "1 s 2", Δ kept as §3c "capital delta"). "Proposed" means no source found prescribes it.

RESULT
1. 15-string normalize() probe saved with per-line verdicts (0 correct, 6 wrong, 9 symbol leaked) — done — _agent/results/850_chemistry_probe_today.txt
2. Note covers all SCOPE classes plus bonds/element symbols: 13 classes, each with Detection, Rule, Wording table, Source, Confidence — done — _agent/research/domain-speech/chemistry.md §2
3. 44 raw→spoken pairs in jsonl shape; parse, lower case, no raw symbols, 0 hits on the 18 banned patterns in math_convention.json — done — _agent/results/852_chemistry_pairs_check.txt (consistency with the note's own rules checked by hand only)
4. Ambiguities (10, with what decides each and what ING-11 could decide) and TERM-1 lexicon needs (42 terms with respellings) — done — note §3, §4

OBSERVATIONS
- Today "→" reads "goes to", a §3c banned wording (850 line 07).
- "SO42−" reads "SO42 minus": the charge merges into the count (850 line 04).
- A decimal with 4 fractional digits is read digit by digit: "180.0634" → "1 8 0, 0 6 3 4"; "180.06" and "12.5" are fine (851). This may be an ING-6 rule for long decimals or a bug.
- "10−10" reads "10 minus 10", not "10 to the minus 10" (850 line 09).
- MathCAT's chemistry rules say "super"/"sub" for scripts, which §3c bans, so the note does not use them.
- No source prescribes spoken forms for charges, oxidation states, M/cm−1, locants, NMR data or configurations, so most rules are "proposed".
- Counts: 13 notation classes, 44 pairs, 7 WebSearch calls (plus 4 WebFetch).

EVIDENCE    _agent/results/850_chemistry_probe_today.txt — 15 strings, today's spoken output, verdict per line
            _agent/results/851_chemistry_decimal_probe.txt — the 4-digit decimal reading, isolated
            _agent/results/852_chemistry_pairs_check.txt — jsonl validation: 44 pairs, 13 classes, 0 issues, 0 banned hits

FILES WRITTEN     _agent/research/domain-speech/chemistry.md
                  _agent/reports/domain-speech-chemistry.md
                  _agent/results/850_chemistry_probe_today.txt
                  _agent/results/851_chemistry_decimal_probe.txt
                  _agent/results/852_chemistry_pairs_check.txt
                  (scratch probe script, outside the repo: /private/tmp/claude-502/-Users-user-Documents-Projects-hearnarro/438f4f28-70de-4560-832e-df73c0c83289/scratchpad/chemprobe.py)
FILES READ BEYOND THE BRIEF     none (PRD ING-11 row read too, since the brief's section 3 names ING-11)

UNVERIFIED  The respellings in note §4 have not been checked against Kokoro (no EVAL-4 run).
            Classroom spoken forms marked "proposed" in the note (e.g. "f e 3 plus", "carbon 14", "proton n m r", "1 s 2").
            Several sources are cited from search-result snippets, not opened pages (marked in note §7).
NOT DONE    none
DRAFTS      none

OUTPUT      (852) pairs: 44 classes: ['abbreviation', 'bond', 'charge', 'electron_configuration', 'formula', 'isotope', 'nomenclature', 'oxidation_state', 'rate_law', 'reaction', 'spectroscopy', 'thermo', 'units']
            rows with issues: 0
            banned patterns: 18 / pairs: 44 banned hits: none
            (850) # TALLY: correct 0, wrong 6 (03,04,07,08,13,14), symbol leaked 9 (01,02,05,06,09,10,11,12,15)
