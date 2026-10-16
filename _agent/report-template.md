# Report template (worker returns exactly this shape)

```
TASK        <short-slug>
STATUS      done | partial | blocked
ASSUMED     any reading of the brief you had to choose (or "none")

RESULT      one line per CLAIM in the brief, in order: claim, status, file. Nothing else here.
OBSERVATIONS things noticed outside the CLAIMS list, plainly labelled; no status.

EVIDENCE    path — one line on what it shows
            path — ...

FILES WRITTEN     every path created or appended, one per line
FILES READ BEYOND THE BRIEF     paths, or "none"

UNVERIFIED  every claim you could not back with a run, one per line, or "none"
NOT DONE    steps you did not complete and why, or "none"
DRAFTS      paths of any outward-facing drafts (PR text, issue text), or "none"

OUTPUT      verbatim: test summary, lint output, command output — whatever ACCEPT names
```
