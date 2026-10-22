"""Copy one page of a PDF into a new single-page PDF (M5 formula fixtures, MATH-1, gate a).

Usage: python scripts/cut_fixture_page.py SRC.pdf PAGE OUT.pdf [--rasterize DPI]

PAGE is 0-based, the same numbering as the ``page`` field of ``*.expected.jsonl``.
With ``--rasterize DPI`` the page is rendered to a grayscale bitmap and written as an
image-only PDF (no text layer), the way the ``scanned_*`` fixtures were made.
Uses pypdfium2 only (Apache-2.0 / BSD-3-Clause, already a dependency).
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

import pypdfium2 as pdfium


def cut_page(src: str, page: int, out: str) -> None:
    """Write page ``page`` (0-based) of ``src`` to ``out`` as a one-page PDF."""
    source = pdfium.PdfDocument(src)
    if not 0 <= page < len(source):
        raise SystemExit(f"page {page} out of range: {src} has {len(source)} pages")
    target = pdfium.PdfDocument.new()
    target.import_pages(source, [page])
    target.save(out)


def rasterize_page(src: str, page: int, out: str, dpi: int) -> None:
    """Render page ``page`` of ``src`` at ``dpi`` and write it as an image-only PDF."""
    source = pdfium.PdfDocument(src)
    if not 0 <= page < len(source):
        raise SystemExit(f"page {page} out of range: {src} has {len(source)} pages")
    src_page = source[page]
    width, height = src_page.get_size()
    bitmap = src_page.render(scale=dpi / 72, grayscale=True)
    pil = bitmap.to_pil().convert("L")
    target = pdfium.PdfDocument.new()
    new_page = target.new_page(width, height)
    image = pdfium.PdfImage.new(target)
    image.set_bitmap(pdfium.PdfBitmap.from_pil(pil))
    image.set_matrix(pdfium.PdfMatrix().scale(width, height))
    new_page.insert_obj(image)
    new_page.gen_content()
    target.save(out)


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("src", help="source PDF")
    ap.add_argument("page", type=int, help="0-based page index")
    ap.add_argument("out", help="output PDF")
    ap.add_argument("--rasterize", type=int, metavar="DPI", help="write an image-only page")
    args = ap.parse_args(argv)
    if args.rasterize:
        rasterize_page(args.src, args.page, args.out, args.rasterize)
    else:
        cut_page(args.src, args.page, args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
