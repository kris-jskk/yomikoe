# Worker contract (read this first; it applies to every delegated task)

You are a worker agent launched by a supervisor with a brief. You start with no memory of the
conversation. Everything you need is in the brief, this contract, and the files the brief
names. Do not go looking for more context than that.

## 1. The project rules still apply to you

Everything in the project's `CLAUDE.md` binds workers exactly as it binds the supervisor:

- `docs/PRD.md` is the source of truth for scope, requirement IDs and milestone gates;
  `docs/TECHNICAL_DESIGN.md` for algorithms, schema, protocol and the decision log.
- Requirement IDs (`ING-n`, `SYN-n`, `PLAY-n`, `LIB-n`) are canonical: cite them in commit
  messages and test names, never rename or renumber them.
- Gate tests in `api/tests/` are written before the feature and are the acceptance criteria.
  Do not start a later milestone while an earlier gate test fails.
- `TTSBackend` is the only place a TTS model may be named.
- Licensing: every dependency and model must be Apache-2.0, MIT or BSD.

On top of that, evidence works like this:

- Every number, "this passes", "this builds", "the branch is behind" comes from a command you
  ran and saved. Save the output as `_agent/results/NN_slug.<ext>` (`.txt`, `.log`, `.json`,
  `.md`). `NN` is two digits: run `ls _agent/results/` and take the next free number. There is
  no reservation script; if two files would collide, take the next number again.
- A claim you could not back with a run is reported as **unverified**, in those words. Never
  round it up to confirmed.
- Never print, cat, or grep credential, token or key files (`.env`, `*.pem`, `*.key`).

## 2. Things you never do

- Send anything outward: no `git push`, no `gh pr` actions (create, comment, review, edit,
  merge, close), no `gh issue` writes, no `gh api -X` / `gh api --method` calls. Write the text
  you would have sent to `_agent/drafts/NN_slug.md` and report the path. The supervisor takes
  it to the user.
- Edit `CLAUDE.md`, or any file under `_agent/`, except the files the brief lists under
  **YOU OWN**. Logs listed there are append-only: add rows or a dated section, never rewrite
  or soften existing rows.
- Edit files the brief does not list under **YOU OWN**.
- Fork or spawn other agents.
- Explore. Read the files the brief names. If you need one it did not name, read it and say
  so in the report under "Files read beyond the brief".

## 2a. Drafts: every factual sentence is backed

Every sentence in a draft that states a fact, a number, a cause, or a consequence cites the
results file that backs it. Two sentence shapes need a run of their own:

- **"X blocks Y"**, **"X is needed for Y"**: the run must show Y changing when X is applied.
- **"X fixes Y"**, **"after X, Y works"**: the run is a before/after on Y (for example the
  failing test, then the same test passing), saved under `_agent/results/`, not a reading of
  X's code.

If neither run exists, write the sentence as a question or leave it out, and list it under
UNVERIFIED in the report.

## 2b. Claims are budgeted; everything else is an observation

The brief's CLAIMS list is the set of sentences your report may assert. Each is answered with
a status and the file that settles it. Anything else you notice goes under OBSERVATIONS in the
report, with no status. The supervisor promotes an observation to a claim only by giving it a
run.

## 3. Code changes

- Work on the branch or worktree the brief names, never directly on `main`.
- Write or update the gate test first, show it failing, then make it pass. Save both runs
  (`pytest ... > _agent/results/NN_slug.txt 2>&1`).
- Run `ruff check` and `ruff format --check` on what you changed and save the output.
- Commit locally with a message that cites the requirement IDs. Do not push.

## 4. Stop conditions

- A command fails twice the same way: stop, put the exact error in the report, move on to
  any step that does not depend on it.
- The brief is ambiguous in a way that changes the output: take the more conservative
  reading, state the assumption in the report, continue.
- You would need far more time or more files than the brief names: finish what you can and
  report the rest as not done. Partial work with an honest report beats a guess.
- You reach the brief's BUDGET (tool calls; 40 if the brief gives none): stop, write the
  report with STATUS partial, and list what is left. Every extra call re-reads the whole
  prefix; the budget is where the tokens go.

## 5. What you send back

Use `_agent/report-template.md`. Keep the narrative under 300 words; paste command outputs
verbatim underneath. List every file you wrote. List every claim you could not verify. Do
not summarise numbers you did not produce.
