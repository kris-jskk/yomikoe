# Brief template (supervisor fills this in; copy the whole thing into the Agent prompt)

The first line of every brief is:
`Read _agent/worker-contract.md (in the project root) before doing anything else.`

```
TASK       <short-slug>                       (e.g. syn-3-gate-test)
MODEL      sonnet | opus                      (set the same value in the Agent tool's model field)
FOLDER     the project root (absolute path)
GOAL       one sentence, what "done" looks like

CONTEXT    at most five bullets. File paths, not prose. Nothing from the conversation
           that is not also in a file (PRD section, design decision, test file, source file).

CLAIMS     the claims this task must settle, numbered, each phrased as a sentence a run can
           make true or false ("the PLAY-2 gate test passes"; "segment fetch p95 is under
           X ms"). The report answers these and nothing else; anything else noticed goes
           under OBSERVATIONS and is not a claim (contract §2b). A consequence claim
           ("X fixes Y", "X blocks Y") names its before/after run under EVIDENCE or is not
           on the list.

BUDGET     tool-call cap for the task (default 40). A worker that reaches it stops and
           reports STATUS partial with what is left.

STEPS      numbered, each with the exact command or the exact file to edit.
           Say which are read-only. Say which may fail and what to do then.

YOU OWN    the files this task may create or append to, by path.
           Everything else is off limits (contract §2).

EVIDENCE   the files under _agent/results/ that must exist when you are done, by path.
           A step with no evidence file is not done.

ACCEPT     what the supervisor will check: a passing command, a named number, a file present.

REPORT     use _agent/report-template.md. Add any task-specific lines here.
```

Sizing guide: a brief over about 500 words usually means the task should be split. A brief
under 100 words usually means the supervisor should do it directly.
