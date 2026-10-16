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
