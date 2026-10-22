```
TASK        domain-speech-biology
STATUS      done
ASSUMED     The probe file 860 from the earlier attempt had 15 strings, each with an output and a verdict, so I
            used it as the step-2 evidence and did not run the probe again (the caller said to). Clinical examples
            use standard textbook doses only (amoxicillin 500 mg three times a day, paracetamol 1 g every 6 hours
            as needed). Where a lecture idiom departs from §3c (unit slash "per", R0 "r nought", log2FC), I wrote
            the idiom, marked it proposed and listed it as an open question.

RESULT      1. 15 probe strings saved with today's normalize() output and verdicts (0 correct, 9 wrong, 6 symbol
               leaked): done (from the earlier run), _agent/results/860_biology_probe_today.txt
            2. All 9 SCOPE classes plus 1 added (10 classes; anatomy and eponyms are a separate class), each with
               Detection/Rule/Wording/Source/Confidence; unsourced rules marked proposed: done,
               _agent/research/domain-speech/biology.md §2
            3. 45 raw→spoken pairs in jsonl shape; the §3c convention checker finds 0 violations: done,
               _agent/results/861_biology_pairs_convention_check.txt
            4. Context ambiguities (§3, 10 items) and lexicon needs (§4, 23 terms with respellings) listed: done,
               _agent/research/domain-speech/biology.md §3–4

OBSERVATIONS
- Today's normalizer turns "→" into "goes to", a wording §3c bans (probe line 03), and reads "p < 0.05" as "p less
  than", without the "is" that §3c requires (line 14). Both come from the MATH-1 symbol fallback and affect more than biology.
- "ΔF508" becomes "delta F508" and "×g" becomes "times g", so the Greek and operator fallback already works in biology text.
  Units with µ and slashes, HGVS variants, genotype suffixes and clinical abbreviations all pass through unchanged.
- The most serious risks are extraction faults that cannot be repaired from the text alone: a flattened 10⁶ becomes "106",
  and a Symbol-font µ extracted as m turns µM into mM, a factor of 1000. Also, a genus initial such as "E." can split a
  sentence. Open questions 8 and §3 cover them.
- Counts: 10 notation classes, 45 pairs, 7 web searches plus 1 page fetch (limit 8). ClearSpeak chemistry,
  NVDA/JAWS, DAISY, CSE, AMA and the ICZN/ICN codes were not consulted, so the rules that would rest on them are marked proposed.
- Total tool calls about 15 of the 30 budgeted.

EVIDENCE    _agent/results/860_biology_probe_today.txt — the 15 strings, today's normalize() output and a verdict per line
            _agent/results/861_biology_pairs_convention_check.txt — 45 pairs across 10 classes, 0 §3c convention violations

FILES WRITTEN     _agent/research/domain-speech/biology.md
                  _agent/results/861_biology_pairs_convention_check.txt
                  _agent/reports/domain-speech-biology.md
FILES READ BEYOND THE BRIEF     api/scripts/check_math_convention.py (function names only, to reuse check() on the pairs);
                  _agent/report-template.md

UNVERIFIED  The outputs in 860 come from the earlier attempt's run. I did not run the probe again in this task.
            All spoken forms marked "proposed" in the note: no source prescribes them.
NOT DONE    none
DRAFTS      none

OUTPUT      pairs: 45 classes: ['anatomy', 'clinical', 'gene', 'lab_unit', 'molecule', 'popgen', 'sequence', 'stats_report', 'taxon', 'variant']
            convention violations: 0
```
