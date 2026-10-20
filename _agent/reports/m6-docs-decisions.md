TASK        m6-docs-decisions
STATUS      done
ASSUMED     - D45–D51 rows were added both to the top "Decision log" table of TECHNICAL_DESIGN.md (beside D41–D44, so the
              log stays a complete index) and as a table in the new "## M6 decisions (D45–D51)" section; the brief named
              only the section. Delete the top-table copies if one place is preferred.
            - "M5–M6 decisions (D36–D40)" renamed "M5 and M7 decisions (D36–D40)" (D38/D39 are now M7, D36/D37/D40 M5).
            - PRD_KINDLE.md line 142 "next milestone close (M5 or M6)" left unchanged: it names the next milestone closes
              generically (a Fire tablet check), not the Classroom milestone; still true with M6 = Domain reading.
            - PRD_DOMAINS.md: in-text "open question N" references became "decision N"; per-row "proposed" in the
              conventions tables was kept (it marks unsourced wordings, not undecided ones; risk row says so).
            - In PRD_DOMAINS.md the 29-row table is under "### Decisions (2026-10-19)" inside "## Decisions and risks";
              columns now "# | Question | Decision | Raised by".

RESULT      1. PRD_DOMAINS.md decided, M6 "Domain reading", Decisions table, D45–D51 "Confirmed 2026-10-19", phase table unchanged — done — 951, 952
            2. PRD.md flow/paragraphs M6 Domain reading, M7 Classroom, M8 Sources; former M6/M7 renumbered in all docs; EVAL-11 row; DOM pointer — done — 950, 951, 954
            3. TECHNICAL_DESIGN.md "## M6 decisions (D45–D51)" with 7 rows, confirmed 2026-10-19; M5–M6 heading renamed — done — 951
            4. No requirement id renamed or renumbered — done — 953 (id sets only gain mentions; PRD_DOMAINS/PRD_KINDLE id sets identical; only new table row is EVAL-11)

OBSERVATIONS
- Renumbered/rewritten former M6/M7 lines per file (954): PRD.md 15 of 15, TECHNICAL_DESIGN.md 6 of 6, PRD_KINDLE.md 12 of 13, PRD_DOMAINS.md 2 of 2.
- PRD.md M6 paragraph carries the dependency "starts after the M5 gate passes (CLAUDE.md milestone rule) and in a fresh session" and the gate (a)/(b) from PRD_DOMAINS.md "Gate test". PRD.md line 46 now mentions EVAL-11 for M6 and D50.
- Open questions in PRD.md for VIEW/NOTE/SRC are relabelled "M7 (was M6)" / "M8 (was M7)" rather than silently renumbered.
- CLAUDE.md and memory still say M6/M7 elsewhere; not touched (supervisor's).

EVIDENCE    _agent/results/950_m6_renumber_before.txt — M6|M7|M8 grep over the four docs before edits (36 lines)
            _agent/results/951_m6_renumber_after.txt — same grep after; DOM/D45–D51 row count 41; stale "M6 Classroom|M7 Sources" check: none
            _agent/results/952_m6_docs_diffstat.txt — git diff --stat docs/
            _agent/results/953_m6_reqid_check.txt — requirement-id sets HEAD vs working tree per file
            _agent/results/954_m6_changed_lines.txt — numstat and renumbered-line counts per file

FILES WRITTEN     docs/PRD_DOMAINS.md
                  docs/PRD.md
                  docs/TECHNICAL_DESIGN.md
                  docs/PRD_KINDLE.md
                  _agent/results/950_m6_renumber_before.txt
                  _agent/results/951_m6_renumber_after.txt
                  _agent/results/952_m6_docs_diffstat.txt
                  _agent/results/953_m6_reqid_check.txt
                  _agent/results/954_m6_changed_lines.txt
                  _agent/reports/m6-docs-decisions.md
                  (scratch: scratchpad/m6-docs-decisions_{domains,prd,td}.py)
FILES READ BEYOND THE BRIEF     _agent/report-template.md (named by the contract)

UNVERIFIED  none
NOT DONE    none (not committed, per brief)
DRAFTS      none

OUTPUT
--- 951 tail
grep -n "^| DOM-\|^| D4[5-9]\|^| D5[01]" docs/PRD_DOMAINS.md docs/TECHNICAL_DESIGN.md | wc -l  ->  41
per file: docs/PRD_DOMAINS.md:27  docs/TECHNICAL_DESIGN.md:14
D45-D51 bullets in PRD_DOMAINS: 7
stale check: M6 Classroom / M7 Sources -> none
--- 952
 docs/PRD.md              | 48 ++++++++++++++++++-----------
 docs/PRD_DOMAINS.md      | 80 +++++++++++++++++++++++++-----------------------
 docs/PRD_KINDLE.md       | 24 +++++++--------
 docs/TECHNICAL_DESIGN.md | 33 ++++++++++++++++----
 4 files changed, 110 insertions(+), 75 deletions(-)
--- 953 (summary)
PRD.md: only additions DOM-1, DOM-26, DOM-27, EVAL-11; TECHNICAL_DESIGN.md: only additions DOM-1/22/23/27, EVAL-10/11, TERM-4;
PRD_KINDLE.md, PRD_DOMAINS.md: identical id set; table-row ids identical except new "| EVAL-11" row in PRD.md
