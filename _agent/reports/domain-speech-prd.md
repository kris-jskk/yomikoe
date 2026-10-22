TASK        domain-speech-prd
STATUS      done
ASSUMED     - "Ordered by how many probe lines they fix": the six probes fail 14-15 of 15 each (flat), so they cannot rank
              domains; the PRD orders phases by judgement (shared grammar, then statistics shared by three notes, then
              per-domain P0 cores), labels the order unverified, and makes "re-run the probes and reorder" the first step.
            - Physics' 7 "wrong + symbol leaked" lines are counted under Wrong in the tally table (3/38/49 of 90).
            - Added a "Shared symbols and cross-domain rules" section between the requirements and the conventions
              sections (needed for claim 2); all other sections follow the Kindle PRD order.
            - Placement recommended: own milestone after M5, before M6 (unnumbered until the user places it).

RESULT      1. docs/PRD_DOMAINS.md exists with the Kindle PRD sections and 27 DOM rows (DOM-1..27), each with priority,
               field, rule with two raw→spoken examples, and "From: note §2.x" — done — _agent/results/880_prd_domains_shape.txt
            2. Every cross-domain rule (→, /, ~, Δ, Ω, ×, ° and zero subscripts, flattened subscripts, ±, *, [ ], :, ′,
               > <, ↑↓, ⟨⟩, p./c./n., Roman numerals, units grammar, numbers, abbreviation reading, profile field) lists
               each note's alternative with its note and a resolution or an open-question number — done — docs/PRD_DOMAINS.md
               "Shared symbols and cross-domain rules" (not run-checkable; a reading of the six notes)
            3. Open questions consolidate the notes' 50 §8 items (8/10/8/8/8/8, counted in 880) into 29 decisions, each
               with a recommendation and the raising notes; every one of the 50 items is mapped — done — docs/PRD_DOMAINS.md,
               counts in _agent/results/880_prd_domains_shape.txt
            4. Overview tally table per domain, cited by file: chemistry 0/6/9, physics 1/7/7, biology 0/9/6, finance 1/7/7,
               history 0/5/10, cs_stats 1/4/10 (correct/wrong/leaked of 15) — done — tally lines re-extracted in
               _agent/results/880_prd_domains_shape.txt

OBSERVATIONS
- Hardest conflicts: (1) the reaction arrow: chemistry "reacts to form" (sourced, MathCAT) vs physics "yields" for nuclear
  and particle reactions, with physics asking for one wording for both; a decay is not a reaction, so the PRD proposes
  two role-keyed wordings (open question 3). (2) E-notation: cs_stats reads `3e-4` "3 e minus 4" (ML practice) while
  physics reads `6.022e23` "6.022 times 10 to the 23"; same token shape, so it must be one rule (open question 6:
  maths reading, "e minus" only in code). (3) Significance stars: finance and biology read "3 stars", cs_stats keeps
  them silent; a statistics row in a biology paper and in an ML paper would sound different (open question 12).
  Runners-up: SD spelled (biology) vs "standard deviation" (cs_stats); "k s p" (chemistry) vs "n sub e" (biology) for
  flattened subscripts; Roman numerals as words (history) vs digits (chemistry, biology).
- Dataset hygiene: physics pairs keep prose case, others lower-case; notes use block "paragraph", EVAL-10 uses "body".
- Word count: 8,687 total; 1,453 outside table rows (the brief targets 1,500-2,500 plus tables; the prose sits just
  under, the content is mostly in tables).
- The 880 open-question regex counts 36 because it also matches the 7 phase rows; the decisions table has 29 rows.

EVIDENCE    _agent/results/880_prd_domains_shape.txt — section headings, 27 DOM rows, word counts, 50 §8 items per note,
            278 pairs per note, the six probe tallies re-extracted from 850-875

FILES WRITTEN     docs/PRD_DOMAINS.md
                  _agent/results/880_prd_domains_shape.txt
                  _agent/reports/domain-speech-prd.md
FILES READ BEYOND THE BRIEF     none (results 860/865/870 were read for their verdict lines, as named in the brief;
                  the history report was grepped for its tally)

UNVERIFIED  - The phase order by payoff (probe counts are flat; judgement only).
            - EVAL-11 adding under 2 s to tier 0 and the domain pass adding under 10 % to normalization time (targets).
            - Whether profile `fields` needs an Alembic migration.
            - How the backend reads years such as 1914 and long decimals (carried from the notes as probes to run).
NOT DONE    none
DRAFTS      none

OUTPUT      (880, verbatim)
$ grep -n "^## " docs/PRD_DOMAINS.md
7:## Overview
27:## Goals, non-goals and success metrics
53:## Users and use cases
64:## Functional requirements
110:## Shared symbols and cross-domain rules
139:## Reading conventions by domain
263:## Architecture and stack
291:## Data model and API
305:## Non-functional requirements
316:## Milestones
334:## Open questions and risks
$ grep -c "^| DOM-" docs/PRD_DOMAINS.md
27
$ wc -w docs/PRD_DOMAINS.md
    8687 docs/PRD_DOMAINS.md
