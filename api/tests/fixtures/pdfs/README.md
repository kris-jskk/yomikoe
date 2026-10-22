# Fixture PDFs (M1 gate)

Twenty PDFs with ground-truth reading order, per PRD "Milestones":

- 5 academic two-column papers
- 5 single-column reports
- 5 scanned pages (no text layer; exercises OCR, ING-2)
- 5 with heavy tables and equations (ING-7)

Each `name.pdf` has a sibling `name.expected.jsonl` with one line per expected segment in reading order.
Only use PDFs you have the right to redistribute (arXiv with a CC license, government reports, your own documents).

## Naming, manifest and expected output

- Files are named `<class>_<nn>_<short-slug>.pdf` (class is `academic`, `report`, `scanned` or `tables`; lowercase ASCII).
- Each PDF is trimmed to its first 4 pages (header/footer detection needs 3+ pages); `scanned` fixtures are 2 rasterized pages with no text layer.
- `manifest.json` lists every fixture (name, class, two_column, source, license, pages); `ATTRIBUTION.md` records source URL, license and license evidence for each.
- `name.expected.jsonl`: one line per expected segment in reading order, fields `order, page, type, text`. Format and scoring are in `_agent/specs/m1-ingestion-interfaces.md`, section "Golden fixture format".
- The `expected.jsonl` files are generated from the pipeline output and hand-corrected in a later task; they do not exist yet.

## Scanned fixtures: provisional ground truth

Each `scanned_*.expected.jsonl` is derived from its source fixture's hand-corrected file
(pages 0–1 only, renumbered): scanned_01 ← academic_01, scanned_02 ← academic_03,
scanned_03 ← report_01, scanned_04 ← tables_03, scanned_05 ← tables_04. They are provisional
until the OCR fallback lands in M4: OCR text will differ from the born-digital text, so these
files will need a second hand-correction against OCR output then. The golden test skips the
scanned class while `ocr_available()` is False.

## Sentence-boundary truth (M2)

Each text fixture (the 15 non-`scanned` ones) has a `name.sentences.txt`: one sentence per line,
prose types only (heading, body, list, caption, footnote; D12), in reading order. It is derived
from `name.expected.jsonl` with only the line breaks moved, so its word stream (`golden_util.words`)
is identical to the expected file's prose; `tests/test_syn_boundaries.py` asserts this.

The breaks were produced by a scripted candidate pass over the expected segments, then a review
of every candidate change against the text (log: `_agent/results/258_boundary_review.md`):
merges after abbreviations (`et seq.`, `Natl.`/`Inst.`/`Stand.`/`Technol.`/`Spec.`/`Publ.`, `Eq.`,
`e.g.`, ...), before lowercase starts and closing brackets/quotes, inside unclosed `(`, and after a
bare section number (`2.1.`); splits where two sentences shared one line. Rejected candidates are
true sentence ends (for example "... in Appendix C." or "... function of x.").

`tests/boundary_util.py` scores a sentence list against this truth: boundaries are word indices
after which a sentence ends, the two word streams are aligned with the word-level edit script, and
precision/recall/F1 are computed over boundaries. The M2 measurement prints a table and the mean;
thresholds are set separately and are not asserted yet.

## Formula fixtures (M5, MATH-1, ING-10, ING-11; PRD milestone 5 gate clause a)

Ten single-page `formula_<nn>_<slug>.pdf` fixtures (class `formula`, `pages: 1`). 01–05 are pages cut
from the `tables_*` and `academic_02` fixtures with `api/scripts/cut_fixture_page.py SRC.pdf PAGE OUT.pdf`
(0-based PAGE; the exact commands are in `ATTRIBUTION.md`); 06–09 are open-licence textbook pages, 08
and 09 with code listings; 10 is image-only (a text page rasterized with the same script's
`--rasterize DPI`). Each has `name.expected.jsonl` (pipeline draft, then hand-corrected: one row per
display equation with its linear text, prose split as on the page, code listings typed `code` even
before the pipeline types them) and `name.spoken.txt`: one line per segment that holds mathematics
(every equation and every sentence with inline maths), written by hand in the reading convention of
`_agent/specs/m5-academic-reading.md` §3c, with a display equation's number spoken first ("equation 3:",
MATH-4); `#` lines are comments. Every manifest entry, including the 20 M1 fixtures, carries a
`profile` (`prose`, `mixed`, `math`; ING-11) that gate clause (e) compares with `compute_profile`.
The M1 golden, quality and boundary tests cover the four M1 classes only.
