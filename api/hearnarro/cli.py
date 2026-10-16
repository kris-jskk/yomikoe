"""Command line entry point: ``hearnarro dump <pdf> [--jsonl] [--no-ocr]`` (M1, ING-2..ING-6)."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence

import pymupdf

from hearnarro.ingestion.pipeline import ingest


def _dump(pdf: str, *, jsonl: bool, ocr: bool) -> int:
    result = ingest(pdf, ocr=ocr)
    by_id = {b.id: b for b in result.blocks}
    for seg in result.segments:
        block = by_id[seg.block_id]
        if jsonl:
            row = {"order": seg.order, "page": block.page, "type": block.type, "text": seg.text}
            print(json.dumps(row, ensure_ascii=False))
        else:
            print(f"{seg.order}\t{block.type}\t{seg.text}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="hearnarro")
    sub = parser.add_subparsers(dest="command", required=True)
    dump = sub.add_parser("dump", help="print a PDF's segments in reading order")
    dump.add_argument("pdf", help="path to the PDF")
    dump.add_argument("--jsonl", action="store_true", help="one JSON object per segment")
    dump.add_argument("--no-ocr", action="store_true", help="skip OCR for pages without text")
    args = parser.parse_args(argv)
    # Keep stdout clean for --jsonl: PyMuPDF writes its messages to stdout by default.
    pymupdf.set_messages(stream=sys.stderr)
    if args.command == "dump":
        return _dump(args.pdf, jsonl=args.jsonl, ocr=not args.no_ocr)
    parser.error(f"unknown command {args.command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
