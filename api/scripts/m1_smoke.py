"""M1 end-to-end smoke: drive a running ``hearnarro serve`` over HTTP (ING-1, ING-4).

Gate mode (default): for each non-scanned fixture in ``tests/fixtures/pdfs/manifest.json``,
upload the PDF, poll until ``ready``/``failed``, page through every stored segment, and score
the prose-only text against ``<stem>.expected.jsonl`` with the gate's word-level measure (D12,
D14). Scoring is imported from ``tests/golden_util.py`` so there is one definition.
Exit 1 if any fixture scores under 0.95, fails its char-mass guard, or does not reach
``ready``, or if the mean is under 0.97.

Each row also reports throughput from the API: ``pages``, ``parse_ms`` (measured by the
ingestion worker, not the client) and ``pg/s``; a total line sums them over the fixtures.

One mode: ``--one some.pdf`` uploads any PDF and prints pages / parse_ms / pages/s, then its
first 20 segments.

    cd api
    .venv/bin/python scripts/m1_smoke.py --base-url http://127.0.0.1:8765
    .venv/bin/python scripts/m1_smoke.py --one ~/Downloads/paper.pdf
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

import httpx

API_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_DIR))

# needs the sys.path line above (one definition of the gate scoring)
from tests.golden_util import (
    char_mass_balanced,
    char_mass_ratio,
    prose_only,
    word_score,
)

DEFAULT_FIXTURES = API_DIR / "tests" / "fixtures" / "pdfs"
DEFAULT_CLASSES = "academic,report,tables"  # "scanned" needs OCR (Tesseract), deferred to M4
PER_PDF_MIN = 0.95
MEAN_MIN = 0.97
PAGE_LIMIT = 500  # the API's documented maximum


def upload(client: httpx.Client, pdf: Path) -> tuple[int, int]:
    """POST the PDF; return (document id, HTTP status). 202 = new, 200 = already stored."""
    with pdf.open("rb") as fh:
        resp = client.post("/documents", files={"file": (pdf.name, fh, "application/pdf")})
    if resp.status_code not in (200, 202):
        raise RuntimeError(f"upload {pdf.name}: HTTP {resp.status_code} {resp.text}")
    return resp.json()["id"], resp.status_code


def wait_settled(client: httpx.Client, doc_id: int, timeout: float) -> dict[str, Any]:
    """Poll GET /documents/{id} until status is ready or failed, or the timeout passes."""
    deadline = time.monotonic() + timeout
    while True:
        doc = client.get(f"/documents/{doc_id}").raise_for_status().json()
        if doc["status"] in ("ready", "failed") or time.monotonic() > deadline:
            return doc
        time.sleep(0.2)


def all_segments(client: httpx.Client, doc_id: int) -> list[dict[str, Any]]:
    """Follow next_from until it is null."""
    rows: list[dict[str, Any]] = []
    start: int | None = 0
    while start is not None:
        page = (
            client.get(f"/documents/{doc_id}/segments", params={"from": start, "limit": PAGE_LIMIT})
            .raise_for_status()
            .json()
        )
        rows.extend(page["segments"])
        start = page["next_from"]
    return rows


def pages_per_s(pages: int | None, parse_ms: int | None) -> float | None:
    if not pages or not parse_ms:
        return None
    return pages / (parse_ms / 1000)


def throughput_cells(doc: dict[str, Any]) -> str:
    """``pages parse_ms pg/s`` cells from the API's page_count and parse_ms."""
    pages, ms = doc.get("page_count"), doc.get("parse_ms")
    rate = pages_per_s(pages, ms)
    return (
        f"{pages if pages is not None else '-':>5} {ms if ms is not None else '-':>8} "
        f"{f'{rate:.1f}' if rate is not None else '-':>6}"
    )


def score(segments: list[dict[str, Any]], expected_path: Path) -> tuple[float, float, float]:
    """(word score, excluded char mass actual, expected) exactly as the M1 golden test does."""
    lines = [json.loads(x) for x in expected_path.read_text().splitlines() if x.strip()]
    expected, excluded_expected = prose_only((r["type"], r["text"]) for r in lines)
    actual, excluded_actual = prose_only((s["type"], s["text"]) for s in segments)
    return (
        word_score(actual, expected),
        char_mass_ratio(actual, excluded_actual),
        char_mass_ratio(expected, excluded_expected),
    )


def run_gate(client: httpx.Client, fixtures: Path, classes: set[str], timeout: float) -> int:
    entries = json.loads((fixtures / "manifest.json").read_text())
    skipped = [e["name"] for e in entries if e["class"] not in classes]
    entries = [e for e in entries if e["class"] in classes]
    header = (
        f"{'fixture':34} {'class':9} {'status':7} {'pages':>5} {'parse_ms':>8} {'pg/s':>6} "
        f"{'segs':>5} {'word':>7} {'mass a/e':>13}  result"
    )
    print(header)
    print("-" * len(header))
    scores: list[float] = []
    failures = 0
    total_pages = 0
    total_ms = 0
    for e in entries:
        name = e["name"]
        doc_id, _ = upload(client, fixtures / f"{name}.pdf")
        doc = wait_settled(client, doc_id, timeout)
        if doc.get("page_count") and doc.get("parse_ms"):
            total_pages += doc["page_count"]
            total_ms += doc["parse_ms"]
        tp = throughput_cells(doc)
        if doc["status"] != "ready":
            failures += 1
            reason = doc.get("fail_reason") or "timed out"
            print(
                f"{name:34} {e['class']:9} {doc['status']:7} {tp} {'-':>5} {'-':>7} {'-':>13}  "
                f"FAIL ({reason})"
            )
            continue
        segs = all_segments(client, doc_id)
        word, mass_a, mass_e = score(segs, fixtures / f"{name}.expected.jsonl")
        ok = word >= PER_PDF_MIN and char_mass_balanced(mass_a, mass_e)
        failures += not ok
        scores.append(word)
        mass = f"{mass_a:.4f}/{mass_e:.4f}"
        print(
            f"{name:34} {e['class']:9} {'ready':7} {tp} {len(segs):5d} {word:7.4f} {mass:>13}  "
            f"{'pass' if ok else 'FAIL'}"
        )
    print("-" * len(header))
    mean = sum(scores) / len(scores) if scores else 0.0
    passed = len(entries) - failures
    print(
        f"fixtures: {len(entries)}  passed: {passed}  failed: {failures}  skipped (class): {len(skipped)}"
    )
    print(f"word-level mean: {mean:.4f} (gate >= {MEAN_MIN}); per-fixture gate >= {PER_PDF_MIN}")
    rate = pages_per_s(total_pages, total_ms)
    print(
        f"pages: {total_pages}  parse time: {total_ms / 1000:.1f} s  "
        f"throughput: {f'{rate:.1f}' if rate is not None else '-'} pages/s"
    )
    ok = failures == 0 and bool(scores) and mean >= MEAN_MIN
    print("RESULT: PASS" if ok else "RESULT: FAIL")
    return 0 if ok else 1


def run_one(client: httpx.Client, pdf: Path, timeout: float) -> int:
    doc_id, code = upload(client, pdf)
    print(
        f"uploaded {pdf.name}: id={doc_id} (HTTP {code}{', already stored' if code == 200 else ''})"
    )
    doc = wait_settled(client, doc_id, timeout)
    print(f"status={doc['status']} pages={doc['page_count']} title={doc['title']!r}")
    rate = pages_per_s(doc.get("page_count"), doc.get("parse_ms"))
    print(
        f"pages: {doc.get('page_count')}  parse_ms: {doc.get('parse_ms')}  "
        f"pages/s: {f'{rate:.1f}' if rate is not None else '-'}"
    )
    if doc["status"] != "ready":
        print(f"fail_reason: {doc.get('fail_reason') or 'timed out'}")
        return 1
    page = client.get(f"/documents/{doc_id}/segments", params={"from": 0, "limit": 20}).json()
    print(f"segments: {page['total']} total; first {len(page['segments'])}:")
    for s in page["segments"]:
        print(f"{s['order']:4d} [{s['type']:8}] {s['text']}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--base-url", default="http://127.0.0.1:8765")
    ap.add_argument("--fixtures-dir", type=Path, default=DEFAULT_FIXTURES)
    ap.add_argument("--classes", default=DEFAULT_CLASSES, help="comma-separated manifest classes")
    ap.add_argument("--timeout", type=float, default=60.0, help="seconds to wait per document")
    ap.add_argument("--one", type=Path, metavar="PDF", help="upload one PDF, print 20 segments")
    args = ap.parse_args(argv)
    with httpx.Client(base_url=args.base_url, timeout=30.0) as client:
        try:
            client.get("/documents").raise_for_status()
        except httpx.HTTPError as exc:
            print(f"cannot reach {args.base_url}: {exc}. Is `hearnarro serve` running?")
            return 2
        if args.one:
            return run_one(client, args.one, args.timeout)
        classes = {c.strip() for c in args.classes.split(",") if c.strip()}
        return run_gate(client, args.fixtures_dir, classes, args.timeout)


if __name__ == "__main__":
    sys.exit(main())
