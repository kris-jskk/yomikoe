# Ground-truth rules for `*.expected.jsonl` (D11; supervisor-owned)

The expected file is what a careful human would read aloud from the PDF, one sentence per line,
in reading order. It is corrected once by hand and then frozen; parser changes are measured
against it, never the other way round.

Format: one JSON object per line, keys `order` (0..N-1, renumbered after editing), `page`
(0-based), `type`, `text`. Only `text` is compared (whitespace-collapsed, stripped).

## Start from the parser's draft

`cd api && .venv/bin/python -m hearnarro dump tests/fixtures/pdfs/<stem>.pdf --jsonl --no-ocr`
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
