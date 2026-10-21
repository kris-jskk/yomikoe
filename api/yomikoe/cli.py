"""Command line entry point (M1).

``yomikoe dump <pdf> [--jsonl] [--no-ocr]`` prints segments (ING-2..ING-6);
``yomikoe check <pdf> [--json] [--no-ocr]`` runs the document quality checklist;
``yomikoe serve [--data-dir DIR] [--host H] [--port N]`` runs the API (ING-1);
``yomikoe renormalize --data-dir DIR (--document-id N | --all)`` re-runs speech
normalization on stored segments and drops the audio cache of the ones that changed (SYN-1);
``yomikoe purge-audio --data-dir DIR --document-id N [--segment-id S] [--voice V]
[--speed X]`` deletes matching ``audio_cache`` rows and their files, printing the count (D19).
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections.abc import Sequence
from pathlib import Path

from yomikoe.ingestion.pipeline import ingest


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
    from yomikoe.quality import check_pdf

    report = check_pdf(pdf, ocr=ocr)
    if as_json:
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(report.table())
    return 0 if report.passed else 1


def _serve(data_dir: str | None, host: str, port: int) -> int:
    import uvicorn

    from yomikoe.app import create_app

    uvicorn.run(create_app(Path(data_dir) if data_dir else None), host=host, port=port)
    return 0


def _needs_mathspeak(text: str) -> bool:
    """True when ``apply_mathspeak`` rewrites a segment without maths spans (MATH-3 units,
    MATH-4 references), so renormalize takes the same path as ingestion."""
    from yomikoe.ingestion.mathspeak.references import rewrite_references
    from yomikoe.ingestion.mathspeak.symbols import rewrite_units

    return bool(rewrite_references(text) or rewrite_units(text))


def renormalize_document(
    conn: sqlite3.Connection, document_id: int, data_dir: Path
) -> tuple[int, int, int]:
    """Rewrite one document's ``normalized_text``/``char_map`` in one transaction.

    Returns (segments changed, audio_cache rows removed, cached files left on disk). Only the
    changed segments lose their cache rows; their files stay as orphans.
    """
    from yomikoe.ingestion.mathspeak import speak_segment
    from yomikoe.ingestion.normalize import normalize
    from yomikoe.storage.db import pack_char_map
    from yomikoe.storage.repo import get_document_profile

    # ING-11, D40: the stored profile (override wins) drives the bracket rule, as at ingestion.
    # MATH-1..4, D36: a segment with math_json is re-spoken from its stored spans, as ingest()
    # did after stage 5; the rest go through normalize alone, as split_sentences did.
    profile = get_document_profile(conn, document_id)

    rows = conn.execute(
        "SELECT s.id, s.text, s.normalized_text, s.char_map, b.type, s.math_json FROM segments s "
        "JOIN blocks b ON b.id = s.block_id WHERE s.document_id = ?",
        (document_id,),
    ).fetchall()
    changed = removed = orphans = 0
    with conn:
        for seg_id, text, old_norm, old_map, block_type, math_json in rows:
            spans = json.loads(math_json) if math_json else []
            if spans or _needs_mathspeak(text):
                norm, cmap = speak_segment(text, spans, profile)
            else:
                norm, cmap = normalize(text, heading=block_type == "heading", profile=profile)
            packed = pack_char_map(cmap)
            if norm == old_norm and packed == bytes(old_map):
                continue
            changed += 1
            conn.execute(
                "UPDATE segments SET normalized_text = ?, char_map = ? WHERE id = ?",
                (norm, packed, seg_id),
            )
            paths = conn.execute(
                "SELECT path FROM audio_cache WHERE segment_id = ?", (seg_id,)
            ).fetchall()
            orphans += sum(1 for (path,) in paths if path and (data_dir / path).exists())
            removed += conn.execute(
                "DELETE FROM audio_cache WHERE segment_id = ?", (seg_id,)
            ).rowcount
    return changed, removed, orphans


def _renormalize(data_dir: str | None, document_id: int | None) -> int:
    from yomikoe.storage.db import connect_sync, db_path, move_legacy_db, resolve_data_dir

    root = resolve_data_dir(data_dir)
    move_legacy_db(root)
    conn = connect_sync(db_path(root))
    try:
        if document_id is None:
            ids = [r[0] for r in conn.execute("SELECT id FROM documents ORDER BY id")]
        else:
            ids = [document_id]
        totals = [0, 0, 0]
        for doc in ids:
            counts = renormalize_document(conn, doc, root)
            totals = [a + b for a, b in zip(totals, counts, strict=True)]
            print(f"document {doc}: {counts[0]} segments changed, {counts[1]} cache rows removed")
    finally:
        conn.close()
    print(f"segments changed: {totals[0]}")
    print(f"cache rows removed: {totals[1]}")
    print(f"orphaned audio files left on disk: {totals[2]}")
    return 0


SPEED_EPSILON = 1e-6  # speeds are REAL; match within float noise


def purge_audio(
    conn: sqlite3.Connection,
    data_dir: Path,
    document_id: int,
    *,
    segment_id: int | None = None,
    voice: str | None = None,
    speed: float | None = None,
) -> int:
    """Delete the matching ``audio_cache`` rows of one document and their files (D19).

    Returns the number of rows removed. Files are removed after the rows are committed.
    """
    where = ["segment_id IN (SELECT id FROM segments WHERE document_id = ?)"]
    params: list[object] = [document_id]
    if segment_id is not None:
        where.append("segment_id = ?")
        params.append(segment_id)
    if voice is not None:
        where.append("voice_id = ?")
        params.append(voice)
    if speed is not None:
        where.append("abs(speed - ?) < ?")
        params += [speed, SPEED_EPSILON]
    clause = " AND ".join(where)
    return _purge_where(conn, data_dir, clause, params)


def purge_segments(conn: sqlite3.Connection, segment_ids: Sequence[int], data_dir: Path) -> int:
    """Delete every ``audio_cache`` row (any voice, speed, backend) of ``segment_ids`` and their
    files; returns the number of rows removed (TERM-2: an override changed these segments)."""
    ids = list(dict.fromkeys(segment_ids))
    removed = 0
    for i in range(0, len(ids), 500):  # stay under SQLite's bound-parameter limit
        chunk = ids[i : i + 500]
        marks = ",".join("?" * len(chunk))
        removed += _purge_where(conn, data_dir, f"segment_id IN ({marks})", chunk)
    return removed


def _purge_where(
    conn: sqlite3.Connection, data_dir: Path, clause: str, params: Sequence[object]
) -> int:
    """Delete the ``audio_cache`` rows matching ``clause``, then their files."""
    with conn:
        paths = [r[0] for r in conn.execute(f"SELECT path FROM audio_cache WHERE {clause}", params)]
        removed = conn.execute(f"DELETE FROM audio_cache WHERE {clause}", params).rowcount
    for rel in paths:
        if rel:
            path = data_dir / rel
            path.unlink(missing_ok=True)
            # remove directories this emptied, never above <data_dir>/audio
            audio_root = data_dir / "audio"
            parent = path.parent
            while parent != audio_root and audio_root in parent.parents:
                try:
                    parent.rmdir()
                except OSError:
                    break
                parent = parent.parent
    return removed


def _purge_audio(
    data_dir: str | None,
    document_id: int,
    segment_id: int | None,
    voice: str | None,
    speed: float | None,
) -> int:
    from yomikoe.storage.db import connect_sync, db_path, move_legacy_db, resolve_data_dir

    root = resolve_data_dir(data_dir)
    move_legacy_db(root)
    conn = connect_sync(db_path(root))
    try:
        removed = purge_audio(
            conn, root, document_id, segment_id=segment_id, voice=voice, speed=speed
        )
    finally:
        conn.close()
    print(f"audio cache entries removed: {removed}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="yomikoe")
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
    serve.add_argument("--data-dir", default=None, help="default: $YOMIKOE_DATA_DIR or ./data")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    renorm = sub.add_parser("renormalize", help="re-run speech normalization on stored segments")
    renorm.add_argument("--data-dir", default=None, help="default: $YOMIKOE_DATA_DIR or ./data")
    which = renorm.add_mutually_exclusive_group(required=True)
    which.add_argument("--document-id", type=int)
    which.add_argument("--all", action="store_true", help="every document")
    purge = sub.add_parser("purge-audio", help="delete cached audio rows and files (D19)")
    purge.add_argument("--data-dir", default=None, help="default: $YOMIKOE_DATA_DIR or ./data")
    purge.add_argument("--document-id", type=int, required=True)
    purge.add_argument("--segment-id", type=int, default=None)
    purge.add_argument("--voice", default=None)
    purge.add_argument("--speed", type=float, default=None)
    args = parser.parse_args(argv)
    if args.command == "dump":
        return _dump(args.pdf, jsonl=args.jsonl, ocr=not args.no_ocr)
    if args.command == "check":
        return _check(args.pdf, as_json=args.json, ocr=not args.no_ocr)
    if args.command == "serve":
        return _serve(args.data_dir, args.host, args.port)
    if args.command == "renormalize":
        return _renormalize(args.data_dir, args.document_id)
    if args.command == "purge-audio":
        return _purge_audio(
            args.data_dir, args.document_id, args.segment_id, args.voice, args.speed
        )
    parser.error(f"unknown command {args.command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
