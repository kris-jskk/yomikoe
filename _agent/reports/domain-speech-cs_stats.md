CORRECTION (2026-10-19): _agent/results/875_cs_stats_probe_today.txt was regenerated with a uniquely named script (domain-speech-cs_stats_probe.py). The first version's RAW/OUT lines were the physics worker's strings, because both tasks wrote probe.py to the shared scratchpad and the physics script overwrote this one between the console run and the saved run. The new outputs match the strings the verdicts describe. Tally unchanged: 1 correct, 4 wrong, 10 symbol leaked.

TASK        domain-speech-cs_stats
STATUS      done
ASSUMED     The probe covers only the normalizer (`normalize(s)[0]`). Backend G2P and num2words were not run, so a verdict about how the voice would mangle a leaked token is a judgement and is unverified. Where cs/stats teacher usage conflicts with §3c, the note keeps §3c's wording in the pairs (matrix inverse "to the minus 1", `N` after `∼` "n of") and lists the conflict as an open question. The only overrides are the context-bounded ones in §3 of the note: `Θ(`/`Ω(` read "big theta/omega", `×` read "by" for dimensions, `:=` read "gets" in algorithm blocks.

RESULT
1. Probe of today's normalize() on 15 strings, each with a verdict: done. Tally: 1 correct, 4 wrong, 10 symbol leaked. Evidence: _agent/results/875_cs_stats_probe_today.txt
2. Note covers every SCOPE class with Detection, Rule, Wording table, Source and Confidence; rules with no source are marked proposed: done. 16 classes; 3 were added beyond the SCOPE list (data units, model and dataset names, grammars and automata are split out). Evidence: _agent/research/domain-speech/cs_stats.md §2
3. At least 30 pairs in the jsonl shape, consistent with §3c: done. 47 pairs across 16 classes; math_convention.json check shows 0 problems. Evidence: _agent/results/877_cs_stats_pairs_convention_check_final.txt
4. Ambiguities and TERM-1 lexicon needs listed: done. 17 ambiguity rows and about 50 lexicon entries. Evidence: _agent/research/domain-speech/cs_stats.md §3, §4

OBSERVATIONS
- Today's MATH-1 fallback speaks `∇` as "nabla", which spec §3c bans (it should be "del"). See probe line 08.
- The fallback reads `Θ` as "theta", not "capital theta" (§3c). It also detaches superscripts: "chi ²(1)", "sigma ²". A combining hat glued to a Greek name comes out as "sigmâ²".
- `~` is not spoken as "distributed as" (probe 14), and `←`, `↑`, `⊤`, `∥`, `ŷ` leak raw.
- The checker's banned list matches "baseline" inside ordinary prose, which is a false positive (run 876). The pair was reworded.
- Counts: 16 notation classes, 47 pairs, 8 WebSearch calls. No search found ClearSpeak or SRE rules specific to statistics accents, so those rows rely on §3c.

EVIDENCE    _agent/results/875_cs_stats_probe_today.txt: 15 raw strings, today's output, and a verdict per line
            _agent/results/876_cs_stats_pairs_convention_check.txt: first check, 1 problem ("baseline")
            _agent/results/877_cs_stats_pairs_convention_check_final.txt: final check, 47 pairs, 0 problems

FILES WRITTEN     _agent/research/domain-speech/cs_stats.md
                  _agent/reports/domain-speech-cs_stats.md
                  _agent/results/875_cs_stats_probe_today.txt
                  _agent/results/876_cs_stats_pairs_convention_check.txt
                  _agent/results/877_cs_stats_pairs_convention_check_final.txt
                  (scratch: probe.py and chk.py in the session scratchpad)
FILES READ BEYOND THE BRIEF     api/scripts/check_math_convention.py (lines 1-90, to reuse check() on the pairs)

UNVERIFIED  How the backend voices leaked tokens such as "0x1F", "3e-4", "KiB" and ".05". The probe stops at the normalizer.
            Every spoken wording marked "proposed" in the note. No source prescribes these wordings.
NOT DONE    none
DRAFTS      none

OUTPUT
(875 tally) TALLY: correct 1, wrong 4, symbol leaked 10.
(877) pairs: 47 unique ids: 47 classes: 16
      keys ok: True
      convention problems: 0
