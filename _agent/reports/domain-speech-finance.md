```
TASK        domain-speech-finance
STATUS      done
ASSUMED     Block "paragraph" used as the brief says, plus "equation" for displays and "table" for table rows
            (the existing math_speech.jsonl uses "equation"/"body"; flagged as open question 8).
            "minus" for parenthesized negatives, reusing §3c unary minus.

RESULT      1. Probe of today's normalize() on 15 finance strings, each labelled — done — _agent/results/865_finance_probe_today.txt
            2. Note covers all 9 SCOPE classes with Detection/Rule/Wording/Source/Confidence, unsourced rules marked proposed — done — _agent/research/domain-speech/finance.md §2
            3. >=30 jsonl pairs consistent with the note and §3c — done (40 pairs, 0 banned/leak/case problems) — _agent/results/867_finance_pairs_check.txt
            4. Context ambiguities and TERM-1 lexicon needs listed — done — finance.md §3 (11 items), §4 (27 rows)

OBSERVATIONS
- Probe: 1 of 15 lines correct (Greek + percent only); 9 symbol leaked or wrong because normalize() has no money,
  bp/pp, multiple, period-abbreviation or table-symbol rules. Downstream misaki already reads "$5", "$4.20",
  "S&P 500", "T+2" well, but drops "bn" and "bp" (unknown token), reads "€3.5m" as "3.5 M euros", "22x" as
  "22 ex", "R²" as "r two", silently drops "***" and "▲", and loses the sign of "(1,234)" and "$(0.12)" (866).
- SYN-4 heuristic disagrees with professional usage on FTSE (spelled, want "footsie"), SEC and AAPL (spoken,
  want spelled), QOQ (spoken, want expanded) (865 tail).
- A parallel worker overwrote my scratchpad probe script (shared scratchpad, same filename probe.py); the saved
  865 file was regenerated from an inline script and contains only finance strings.
- The probe's raw "Σ" read as "sigma" rather than "capital sigma"/"the sum" (865 line 14).

EVIDENCE    _agent/results/865_finance_probe_today.txt — 15 strings, normalize() output, verdicts; SYN-4 decide() on 34 tokens
            _agent/results/866_finance_misaki_g2p.txt — misaki G2P phonemes for 20 finance tokens normalize() leaves alone
            _agent/results/867_finance_pairs_check.txt — 40 pairs parse, unique ids, 0 problems; block values in math_speech.jsonl

FILES WRITTEN     _agent/research/domain-speech/finance.md
                  _agent/results/865_finance_probe_today.txt
                  _agent/results/866_finance_misaki_g2p.txt
                  _agent/results/867_finance_pairs_check.txt
                  _agent/reports/domain-speech-finance.md
FILES READ BEYOND THE BRIEF     api/hearnarro/synthesis/compat/ (located via grep only, to import the num2words shim for 866)

UNVERIFIED  All §4 respellings except FTSE and REIT (sourced) are proposed, not checked against a dictionary.
            How the Kokoro voice actually sounds for these strings (866 is phonemes, no audio).
            Style-guide rules from Bloomberg/FT/Economist/CFA/AEA/SEC: not consulted within the 8-search budget.
NOT DONE    none (ClearSpeak/NVDA/DAISY finance coverage not searched; listed in note §7)
DRAFTS      none

COUNTS      notation classes covered: 9 (all SCOPE classes; regression and table split as in SCOPE)
            pairs written: 40
            web searches used: 8

OUTPUT      (867)
pairs parsed: 40 ids unique: True
keys ok: True
classes: {'currency': 10, 'percent_points': 6, 'period': 4, 'abbrev': 4, 'econ': 4, 'regression': 3, 'formula': 4, 'table': 2, 'date': 3}
rows with problems: 0
math_speech.jsonl block values: {'equation': 87, 'body': 71}
finance block values: {'paragraph': 32, 'equation': 4, 'table': 4}
```
