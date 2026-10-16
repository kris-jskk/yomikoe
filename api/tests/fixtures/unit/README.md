# Unit-test PDFs (ING-2, D13)

Two tiny PDFs written byte by byte by a throwaway script (no PDF library, no new
dependency), used by `tests/test_ing1_extract.py`:

- `text.pdf` — one 612x792 page: a Helvetica line "Hello world. Hello world. Hello world.",
  a Helvetica-Bold line "Bold heading", a Times-Italic line "Italic words" followed by a
  7 pt Helvetica "1" raised 4 pt (superscript), the rotated stamp "arXiv:1234.5678" drawn
  90 degrees counter-clockwise at x=30, and a 1x1 grey image XObject scaled to 100x100 pt at
  (72, 400) in PDF coordinates (top-left bbox 72, 292, 172, 392).
- `blank.pdf` — one 612x792 page with no content stream.

Both use only the base-14 fonts, so no font files are embedded. Created 2026-10-16 for the
D13 extractor swap (pdfplumber + pypdfium2).
