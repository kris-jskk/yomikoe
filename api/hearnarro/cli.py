"""Command line entry point (M1).

``hearnarro dump <pdf> [--jsonl] [--no-ocr]`` prints segments (ING-2..ING-6);
``hearnarro check <pdf> [--json] [--no-ocr]`` runs the document quality checklist;
``hearnarro serve [--data-dir DIR] [--host H] [--port N]`` runs the API (ING-1).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

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


def _check(pdf: str, *, as_json: bool, ocr: bool) -> int:
    from hearnarro.quality import check_pdf

    report = check_pdf(pdf, ocr=ocr)
    if as_json:
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(report.table())
    return 0 if report.passed else 1


def _serve(data_dir: str | None, host: str, port: int) -> int:
    import uvicorn

    from hearnarro.app import create_app

    uvicorn.run(create_app(Path(data_dir) if data_dir else None), host=host, port=port)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="hearnarro")
    sub = parser.add_subparsers(dest="command", required=True)
    dump = sub.add_parser("dump", help="print a PDF's segments in reading order")
    dump.add_argument("pdf", help="path to the PDF")
    dump.add_argument("--jsonl", action="store_true", help="one JSON object per segment")
    dump.add_argument("--no-ocr", action="store_true", help="skip OCR for pages without text")
    check = sub.add_parser("check", help="run the document quality checklist on a PDF")
    check.add_argument("pdf", help="path to the PDF")
    check.add_argument("--json", action="store_true", help="print the structured result")
    check.add_argument("--no-ocr", action="store_true", help="skip OCR for pages without text")
    serve = sub.add_parser("serve", help="run the HTTP API")
    serve.add_argument("--data-dir", default=None, help="default: $HEARNARRO_DATA_DIR or ./data")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    args = parser.parse_args(argv)
    if args.command == "dump":
        return _dump(args.pdf, jsonl=args.jsonl, ocr=not args.no_ocr)
    if args.command == "check":
        return _check(args.pdf, as_json=args.json, ocr=not args.no_ocr)
    if args.command == "serve":
        return _serve(args.data_dir, args.host, args.port)
    parser.error(f"unknown command {args.command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
