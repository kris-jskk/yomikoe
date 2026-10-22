# Report: domain-speech-dataset

STATUS      done (claims 1-4 settled; budget 25, about 16 tool calls used)
MODEL       sonnet

## Narrative
The six notes' jsonl blocks (section 5) were extracted by script, tagged with "domain", validated and written to
one file. The convention checker flags 15 pairs, all in the physics note and all for upper-case letters (physics
keeps sentence case in `spoken`; the other five notes are lower case). No banned wording or raw symbol anywhere.
The findings file holds the tally, 19 normalizer defects (D1-D19) and 16 wording conflicts (C1-C16).
The brief's "capital delta vs change in" conflict does not occur: no note says "change in".

## Counts
- total pairs 278 (chemistry 44, physics 57, biology 45, finance 40, history 45, cs_stats 47)
- defects 19; wording conflicts 16

## CLAIMS
1. settled: 278 lines parse, ids unique, keys exactly id/class/raw/spoken/block/domain. Evidence: _agent/results/885_domain_speech_jsonl_check.txt
2. settled with violations: 15 violations, all "upper-case letters", ids physics_01, 03, 06, 07, 10, 18, 21, 22, 24, 31, 39, 44, 49, 53, 54. Evidence: 885
3. settled: defect table D1-D19 in cross-domain-findings.md section 2; D7, D8, D9 verified in one domain only (second domain flagged unverified).
4. settled: conflict table C1-C16 in section 3. Evidence: _agent/results/886_wording_conflicts_grep.txt

## Probe tally (correct / wrong / leaked of 15)
chemistry 0/6/9; physics 1/7/7; biology 0/9/6; finance 1/7/7; history 0/5/10; cs_stats 1/4/10 (total 3/38/49).
Biology, finance and history have no tally line; counted from verdict lines. The finance report's "9 leaked or wrong" disagrees with its own verdicts (14); not used.

## OBSERVATIONS
- cs_stats note offers "big omega/theta" (rows 48-49) while its own row 420 and §3c say "capital"; one of the two needs to go.
- biology ΔF508 "delta f 508" departs from §3c's capital prefix.
- E-notation: physics "times 10 to the 23" vs cs_stats "3 e minus 4".
- Line cites in the findings file are verdict-line numbers computed from each file's layout; I spot-checked history and chemistry, not every one.

## UNVERIFIED
- Whether Kokoro voices the leaked tokens (probes stop at normalize()).
- Line numbers for 870, 875 and 865 cites beyond the lines I opened.

## FILES WRITTEN
_agent/research/domain-speech/domain_speech.jsonl
_agent/research/domain-speech/cross-domain-findings.md
_agent/reports/domain-speech-dataset.md
_agent/results/885_domain_speech_jsonl_check.txt
_agent/results/886_wording_conflicts_grep.txt
FILES READ BEYOND THE BRIEF: api/scripts/math_convention.json (full), reports' OBSERVATIONS (as briefed), none else.

## OUTPUT (885)
total 278, duplicate ids none, key mismatches none; violations: 15 (upper-case, physics)
