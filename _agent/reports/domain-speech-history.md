TASK        domain-speech-history
STATUS      done
ASSUMED     Roman numerals after structural words keep today's cardinal-word rule (result 871); regnal Roman numerals become ordinal words, an explicit exception to "numbers stay digits", listed as open question 1. Spoken column lower case, as in math_speech.jsonl. "ibid" defaults to the word with TERM-4 expansion as an option (open question 3).

RESULT
1. Today's normalize() output for 15 history strings saved with per-line verdicts — done — _agent/results/870_history_probe_today.txt (0 correct, 5 wrong, 10 symbol leaked)
2. Note covers every SCOPE class (10 class sections, 13 class labels incl. scripture_ref, military, coordinates split out) with Detection, Rule, Wording table, Source, Confidence; unsourced rules marked proposed — done — _agent/research/domain-speech/history.md §2
3. >=30 raw→spoken pairs in jsonl shape — done, 45 pairs, parse/keys/lower-case/no-"comma" checked — _agent/results/872_history_pairs_check.txt; consistency with §3c is by authoring (ranges "to", `*` "star", `°` "degrees", `/` "over" kept in maths) — not machine-checked against check_math_convention.py: unverified
4. Context ambiguities (13 rows) and TERM-1 lexicon needs (30 respellings) listed — done — note §3 and §4

OBSERVATIONS
- `[2019] UKSC 41` loses its year today: the ING-6 numeric-citation rule drops "[2019]" (870 line 11).
- `51°30′N` becomes "51 degrees30′N" (no space, prime leaks) (871).
- In prose `p < 0.05` reads "p less than 0.05", without §3c's "is" (871).
- `Vol. III` becomes "Vol. three" but `ch. IV` stays raw; `WWII` stays raw while `World War II` becomes "World War two" (871).
- Whether the backend speaks 1914 as "nineteen fourteen" was not probed; it matters more than any class here (open question 2).
- Searches: 8 of 8 used; the search on [sic]/ibid in narration found nothing usable. Chicago, OSCOLA, Bluebook, SBL, OCD and BBC Pronunciation Unit were not consulted; statements attributed to them in the note are from knowledge and labelled unverified there.

EVIDENCE    _agent/results/870_history_probe_today.txt — 15 strings, today's spoken output, verdict per line, probe script
            _agent/results/871_history_probe_roman_structural.txt — Roman numerals after structural words, coordinates, *, < > in prose today
            _agent/results/872_history_pairs_check.txt — 45 pairs parse, keys, unique ids, lower case, class counts, sections 1-8 present

FILES WRITTEN     _agent/research/domain-speech/history.md
                  _agent/results/870_history_probe_today.txt
                  _agent/results/871_history_probe_roman_structural.txt
                  _agent/results/872_history_pairs_check.txt
                  _agent/reports/domain-speech-history.md
FILES READ BEYOND THE BRIEF     none (normalize.py read as a definition/constant listing only)

UNVERIFIED  pair consistency with spec §3c not run through api/scripts/check_math_convention.py
            backend reading of years, ordinals ("18th"), decimals ("4.1") and SYN-4 spelling of BC/BCE/HMS not probed
            style-guide attributions (Chicago, OCD, SBL, Leipzig, Kant/TLP conventions) not fetched
NOT DONE    none
DRAFTS      none

COUNTS      notation classes covered: 10 sections (13 class labels); pairs written: 45; web searches used: 8

OUTPUT      (872)
pairs: 45
keys ok: True
ids unique: True
spoken lower case: True
word 'comma' absent: True
classes: {'regnal': 6, 'date': 8, 'citation': 5, 'classical_ref': 5, 'scripture_ref': 3, 'legal': 7, 'money_measure': 2, 'military': 1, 'coordinates': 1, 'editorial': 2, 'philosophy_lit': 3, 'linguistics': 2}
notation class sections (2.x): 10
top sections: ['1', '2', '3', '4', '5', '6', '7', '8']
