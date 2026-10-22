# Ground-truth rules for `*.expected.jsonl` (D11; supervisor-owned)

The expected file is what a careful human would read aloud from the PDF, one sentence per line,
in reading order. It is corrected once by hand and then frozen; parser changes are measured
against it, never the other way round.

Format: one JSON object per line, keys `order` (0..N-1, renumbered after editing), `page`
(0-based), `type`, `text`. Only `text` is compared (whitespace-collapsed, stripped).

## Start from the parser's draft

`cd api && .venv/bin/python -m yomikoe dump tests/fixtures/pdfs/<stem>.pdf --jsonl --no-ocr`
is the draft. Keep its sentence boundaries and its extracted text verbatim wherever the order is
right; the test measures order, not extraction quality. Do not retype table cells or fix ligature
glitches. Change only what the rules below require.

## What a reader hears, in this order

1. Title, then author names, then affiliations (one segment each, as the draft splits them).
2. Abstract heading and abstract, then the body in column order: left column top to bottom, then
   right column, page by page. A full-width element (wide figure, table, heading spanning both
   columns) is read where it sits; text above it in both columns comes first, text below it after.
3. Headings in place. Captions in place with their figure/table. List items in place.
4. Table text where the table sits, as the draft extracted it (ING-7 row prose is M4).
5. Equations where they sit, as extracted.
6. Footnotes at the end of the page they appear on, after both columns.
7. A sentence that continues across a column or page break is ONE segment containing the whole
   sentence, de-hyphenated ("respec-" + "tively" → "respectively"). If the draft split it into
   fragments because of a wrong order, join the fragments into one line.

## What is dropped

- Running headers and footers, page numbers, "Page N of M".
- The arXiv margin stamp ("arXiv:2610.xxxxx [cs.XX] 14 Oct 2026").
- Email addresses and lines that are only emails or URLs.
- Empty or whitespace-only segments.
- Cover-page boilerplate that is not meant to be read (NIST reports: the DOI line, the
  "This publication is available free of charge from" line, the department/agency signature
  block on the cover) — keep the title, subtitle, authors, and any abstract/body text.

## Type values

Use the draft's `type` unless you move or join a line; a joined line takes the first fragment's
type. Allowed: heading, body, caption, footnote, table, equation, list.

## Record

For each fixture, note in the results file: segments in draft, segments in final, lines moved,
lines dropped, lines joined, and one sentence on the main parser error seen (or "none").

## Amendment 2026-10-16 (decision D12, user-approved): prose-only comparison

Measured on 2026-10-16 (results 55, 56, 70): the remaining gap to the gate was dominated by text
a listener should never hear, and by inline-math fragments the three reviewers handled
differently. Three rules change; everything above still holds.

1. **Figure-internal text is dropped**, from the parser (type `figure`, never read) and from the
   expected files. Definition: a segment whose source raw blocks are all at least 80% inside a
   figure region (a stage-1 image bbox, or the bbox of a transitive union of overlapping
   `get_drawings()` rects covering 2%–80% of the page). Captions are never figure-internal. The
   removal list per fixture is `_agent/results/56_figure_text_removed.jsonl` (0 unmatched).
2. **Inline-math fragments are joined into their host sentence.** A fragment is a block of at
   most a few characters or symbols (sub/superscripts, operators, "r )∥2", "∫", "π :=") that
   vertically overlaps a prose line. Whether the draft emitted it in order or out of order, the
   expected file has ONE segment for the sentence, with the fragment text placed at its reading
   position, separated by single spaces. Display equations (their own block, on their own line)
   stay separate segments typed `equation`.
3. **The golden comparison is prose-only.** Both sequences keep only segments whose type is
   heading, body, list, caption or footnote. Table and equation internals are excluded until
   ING-7 (M4) defines how they are read; the test also asserts that the number of excluded
   segments on the actual side is within 15% of the expected side, so misclassifying prose as
   table cannot hide an error.

## Amendment 2026-10-16 (decision D14, user-approved): word-level gate

The sentence-level comparison penalized segment-boundary differences that are artifacts of the
extractor the truth was drawn from (results 144, 146; supervisor log 2026-10-16). The M1 gate is now:

- **Score:** both sides keep prose segments only (rule 3); join their texts with single spaces,
  lowercase, split on whitespace, strip ASCII and typographic punctuation from each token, drop
  empty tokens. `score = 1 − seq_levenshtein(actual_words, expected_words) / len(expected_words)`.
  Thresholds unchanged: ≥ 0.95 per fixture, ≥ 0.97 mean.
- **Guard:** excluded character mass (chars in table/equation segments ÷ chars in all segments)
  on each side must agree within 0.05 absolute. Replaces the segment-count guard.
- **Diagnostic:** the sentence-level score (rule 3 definition) is still computed and printed per
  fixture, never asserted. Sentence boundaries are covered by the stage-5 unit tests.
