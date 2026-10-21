# EVAL-9 listening rubric

Listen to each clip once, at a normal volume, in the order the sheet lists them, without
replaying or comparing clips side by side; for each clip score **naturalness** from 1 to 5
(1 = robotic or hard to follow, 3 = clearly synthetic but easy to listen to, 5 = could pass
for a careful human reader), score **pacing** from 1 to 5 (1 = far too fast, too slow or
uneven, 3 = acceptable, 5 = natural rhythm with pauses where a reader would pause), count
**pronunciation errors** (each word, number, abbreviation or symbol read wrongly, skipped or
garbled counts once), and note anything odd (clicks, cut-off endings, wrong emphasis). Write
your name after `listener:` in the sheet header before you start.

## Columns

| column | meaning | allowed values |
|---|---|---|
| clip | the audio file, `<sentence_id>__<voice>.wav` (filled by `prepare`) | do not edit |
| sentence | the text the voice was given (filled by `prepare`) | do not edit |
| naturalness | how human and pleasant the voice sounds | integer 1–5 |
| pacing | speed, rhythm and pauses | integer 1–5 |
| pron_errors | words read wrongly, skipped or garbled | integer 0 or more |
| notes | anything odd, free text | optional |

Every naturalness, pacing and pron_errors cell must be filled; `ingest` rejects a sheet with a
blank or out-of-range cell. When done, run from `api/`:
`.venv/bin/python -m yomikoe.evals listening ingest <path to sheet.md>`.
