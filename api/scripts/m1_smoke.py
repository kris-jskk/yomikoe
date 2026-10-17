"""M1 end-to-end smoke: drive a running ``hearnarro serve`` over HTTP (ING-1, ING-4).

Gate mode (default): for each non-scanned fixture in ``tests/fixtures/pdfs/manifest.json``,
upload the PDF, poll until ``ready``/``failed``, page through every stored segment, and score
the prose-only text against ``<stem>.expected.jsonl`` with the gate's word-level measure (D12,
D14). Scoring is imported from ``tests/golden_util.py`` so there is one definition.
Exit 1 if any fixture scores under 0.95, fails its char-mass guard, or does not reach
``ready``, or if the mean is under 0.97.

Each row also reports throughput from the API: ``pages``, ``parse_ms`` (measured by the
ingestion worker, not the client) and ``pg/s``; a total line sums them over freshly parsed fixtures (HTTP 202). Fixtures the server already held
(HTTP 200) show status ``cached`` and are left out of the total.

Every document also runs the quality checklist (``hearnarro.quality``) on the segments the
API returns (text + block type; title from ``GET /documents/{id}``). The ``checks`` column
shows ``ok`` or ``N fail``; the failing checks are listed under the table with up to three
examples. A ``quality:`` line counts documents with failing checks; it is printed but never
changes the exit code (RESULT stays score-based). ``empty_text_document`` cannot be judged over
HTTP (no per-page character count) and always passes here.

One mode: ``--one some.pdf`` uploads any PDF and prints pages / parse_ms / pages/s, then its
first 20 segments and its checklist.

User documents: ``--user-docs [DIR]`` (default ``tests/user_docs/``, git-ignored PDFs) uploads
every PDF in DIR after the gate and prints pages / parse_ms / pg/s / segs / checks. No score
(user documents have no expected file).

Audio pass (M2): ``--audio`` runs after the gate (and ``--user-docs``) over every ``ready``
document the server holds (SYN-1, SYN-2, SYN-3, SYN-6). It checks ``GET /voices`` (>= 6
voices, both genders), then for the first 3 segments with words of each document fetches
``GET /audio`` at speeds 1.0, 1.25 and 2.5 with the first voice and checks: HTTP 200, an audio
content type, ``X-Duration-Ms`` > 0, ``X-Timestamps`` sorted, non-overlapping and within the
duration, char spans inside the segment text, and ``HEAD`` 200 afterwards. A ``HEAD`` before
the GET shows whether the entry was already cached (lookahead, SYN-5), so TTFA reads as a
cold or warm figure. It does not care which backend the server runs (fake or Kokoro). Any
audio failure makes the exit code 1.

    cd api
    .venv/bin/python scripts/m1_smoke.py --base-url http://127.0.0.1:8765
    .venv/bin/python scripts/m1_smoke.py --audio
    .venv/bin/python scripts/m1_smoke.py --user-docs
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
from hearnarro.quality import QSeg, QualityReport, run_checks
from tests.golden_util import (
    char_mass_balanced,
    char_mass_ratio,
    prose_only,
    word_score,
)

DEFAULT_FIXTURES = API_DIR / "tests" / "fixtures" / "pdfs"
DEFAULT_USER_DOCS = API_DIR / "tests" / "user_docs"
MAX_SHOWN_EXAMPLES = 3
DEFAULT_CLASSES = "academic,report,tables"  # "scanned" needs OCR (Tesseract), deferred to M4
PER_PDF_MIN = 0.95
MEAN_MIN = 0.97
PAGE_LIMIT = 500  # the API's documented maximum
AUDIO_SPEEDS = (1.0, 1.25, 2.5)
AUDIO_SEGMENTS = 3
MIN_VOICES = 6
AUDIO_TYPES = ("audio/wav", "audio/ogg", "audio/webm")


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


def quality(doc: dict[str, Any], segments: list[dict[str, Any]], name: str) -> QualityReport:
    """Run the checklist on API segments; ``doc`` is the GET /documents/{id} body."""
    segs = [QSeg(s["text"], s["type"]) for s in segments]
    # no per-page char count over HTTP: empty_text_document cannot fire here
    return run_checks(segs, title=doc.get("title"), max_page_chars=0, source=name)


def checks_cell(report: QualityReport | None) -> str:
    if report is None:
        return "-"
    n = sum(not c.passed for c in report.checks)
    return "ok" if n == 0 else f"{n} fail"


def print_failing(reports: list[QualityReport]) -> int:
    """List each document's failing checks with up to 3 examples; return how many failed."""
    bad = [r for r in reports if not r.passed]
    if bad:
        print("failing checks:")
    for r in bad:
        for c in r.checks:
            if not c.passed:
                ex = " | ".join(e[:80] for e in c.examples[:MAX_SHOWN_EXAMPLES])
                print(f"  {r.source}: {c.name} ({c.count}): {ex}")
    return len(bad)


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
        f"{'segs':>5} {'word':>7} {'mass a/e':>13} {'checks':>7}  result"
    )
    print(header)
    print("-" * len(header))
    scores: list[float] = []
    failures = 0
    total_pages = 0
    total_ms = 0
    fresh = 0
    reports: list[QualityReport] = []
    for e in entries:
        name = e["name"]
        doc_id, code = upload(client, fixtures / f"{name}.pdf")
        cached = code == 200  # deduplicated: parsed by an earlier upload, not this run
        fresh += not cached
        doc = wait_settled(client, doc_id, timeout)
        if not cached and doc.get("page_count") and doc.get("parse_ms"):
            total_pages += doc["page_count"]
            total_ms += doc["parse_ms"]
        tp = throughput_cells(doc)
        if doc["status"] != "ready":
            failures += 1
            reason = doc.get("fail_reason") or "timed out"
            print(
                f"{name:34} {e['class']:9} {doc['status']:7} {tp} {'-':>5} {'-':>7} {'-':>13} "
                f"{'-':>7}  "
                f"FAIL ({reason})"
            )
            continue
        segs = all_segments(client, doc_id)
        word, mass_a, mass_e = score(segs, fixtures / f"{name}.expected.jsonl")
        ok = word >= PER_PDF_MIN and char_mass_balanced(mass_a, mass_e)
        failures += not ok
        scores.append(word)
        mass = f"{mass_a:.4f}/{mass_e:.4f}"
        report = quality(doc, segs, name)
        reports.append(report)
        print(
            f"{name:34} {e['class']:9} {'cached' if cached else 'ready':7} {tp} {len(segs):5d} "
            f"{word:7.4f} {mass:>13} {checks_cell(report):>7}  {'pass' if ok else 'FAIL'}"
        )
    print("-" * len(header))
    n_bad = print_failing(reports)
    mean = sum(scores) / len(scores) if scores else 0.0
    passed = len(entries) - failures
    print(
        f"fixtures: {len(entries)}  passed: {passed}  failed: {failures}  skipped (class): {len(skipped)}"
    )
    print(f"word-level mean: {mean:.4f} (gate >= {MEAN_MIN}); per-fixture gate >= {PER_PDF_MIN}")
    rate = pages_per_s(total_pages, total_ms)
    if entries and fresh == 0:
        print("throughput: n/a (all documents cached; use a fresh --data-dir to measure)")
    else:
        print(
            f"pages: {total_pages}  parse time: {total_ms / 1000:.1f} s  "
            f"throughput: {f'{rate:.1f}' if rate is not None else '-'} pages/s"
            + (f"  (excludes {len(entries) - fresh} cached)" if fresh < len(entries) else "")
        )
    ok = failures == 0 and bool(scores) and mean >= MEAN_MIN
    print("RESULT: PASS" if ok else "RESULT: FAIL")
    print(f"quality: {n_bad} documents with failing checks (informational; exit code unchanged)")
    return 0 if ok else 1


def run_user_docs(client: httpx.Client, folder: Path, timeout: float) -> None:
    """Upload every PDF in ``folder``; throughput and checklist only (no expected file)."""
    pdfs = sorted(folder.glob("*.pdf"))
    print()
    print(f"user documents: {folder} ({len(pdfs)} PDFs)")
    if not pdfs:
        return
    header = (
        f"{'document':44} {'status':7} {'pages':>5} {'parse_ms':>8} {'pg/s':>6} {'segs':>5} "
        f"{'checks':>7}"
    )
    print(header)
    print("-" * len(header))
    reports: list[QualityReport] = []
    for pdf in pdfs:
        doc_id, code = upload(client, pdf)
        doc = wait_settled(client, doc_id, timeout)
        tp = throughput_cells(doc)
        name = pdf.stem[:44]
        if doc["status"] != "ready":
            reason = doc.get("fail_reason") or "timed out"
            print(f"{name:44} {doc['status']:7} {tp} {'-':>5} {'-':>7}  ({reason})")
            continue
        segs = all_segments(client, doc_id)
        report = quality(doc, segs, pdf.name)
        reports.append(report)
        status = "cached" if code == 200 else "ready"
        print(f"{name:44} {status:7} {tp} {len(segs):5d} {checks_cell(report):>7}")
    print("-" * len(header))
    n_bad = print_failing(reports)
    print(f"quality (user documents): {n_bad} documents with failing checks (informational)")


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
    report = quality(doc, all_segments(client, doc_id), pdf.name)
    print(f"checks: {checks_cell(report)}")
    print_failing([report])
    return 0


def check_timestamps(ts: Any, duration_ms: int, text: str) -> list[str]:
    """Problems with one X-Timestamps list (empty list = valid)."""
    if not isinstance(ts, list) or not ts:
        return ["timestamps empty or not a list"]
    problems: list[str] = []
    prev_end = 0
    prev_char = 0
    for i, t in enumerate(ts):
        s_ms, e_ms, cs, ce = t["start_ms"], t["end_ms"], t["char_start"], t["char_end"]
        if not 0 <= s_ms <= e_ms:
            problems.append(f"word {i}: start {s_ms} > end {e_ms}")
        if s_ms < prev_end:
            problems.append(f"word {i}: starts at {s_ms} before previous end {prev_end}")
        if e_ms > duration_ms:
            problems.append(f"word {i}: end {e_ms} past duration {duration_ms}")
        if not 0 <= cs < ce <= len(text) or cs < prev_char:
            problems.append(f"word {i}: char span {cs}..{ce} outside text (len {len(text)})")
        elif not text[cs:ce].strip():
            problems.append(f"word {i}: char span {cs}..{ce} is blank")
        prev_end, prev_char = max(prev_end, e_ms), max(prev_char, ce)
    return problems


def check_voices(client: httpx.Client) -> tuple[str | None, list[str]]:
    """(first voice id, problems) from GET /voices."""
    resp = client.get("/voices")
    if resp.status_code != 200:
        return None, [f"/voices: HTTP {resp.status_code}"]
    voices = resp.json()
    genders = {v.get("gender") for v in voices}
    problems = []
    if len(voices) < MIN_VOICES:
        problems.append(f"/voices: {len(voices)} voices (< {MIN_VOICES})")
    if not {"female", "male"} <= genders:
        problems.append(f"/voices: genders {sorted(map(str, genders))} (need female and male)")
    backends = sorted({v.get("backend") for v in voices})
    print(f"voices: {len(voices)} from {backends}; genders {sorted(map(str, genders))}")
    return (voices[0]["id"] if voices else None), problems


def run_audio(client: httpx.Client, timeout: float) -> int:
    """Audio pass over every ready document; return the number of failures."""
    print()
    print("audio pass")
    voice, problems = check_voices(client)
    failures = len(problems)
    for p in problems:
        print(f"  FAIL {p}")
    if voice is None:
        print("audio: 0 requests, 1 failures (no voices)")
        return failures or 1
    docs = [d for d in client.get("/documents").raise_for_status().json() if d["status"] == "ready"]
    header = (
        f"{'document':34} {'seg':>6} {'speed':>5} {'pre':>4} {'code':>4} {'type':10} "
        f"{'dur_ms':>7} {'words':>5} {'bytes':>8} {'ttfa_ms':>8} {'head':>4}  result"
    )
    print(f"first voice: {voice}; {len(docs)} ready documents")
    print(header)
    print("-" * len(header))
    ttfas: list[float] = []
    n_req = 0
    for doc in docs:
        name = str(doc.get("filename") or doc.get("title") or doc["id"])[:34]
        segs = [s for s in all_segments(client, doc["id"]) if s["normalized_text"].split()]
        for seg in segs[:AUDIO_SEGMENTS]:
            for speed in AUDIO_SPEEDS:
                n_req += 1
                url, params = f"/audio/{seg['id']}", {"voice": voice, "speed": speed}
                pre = client.head(url, params=params).status_code
                t0 = time.perf_counter()
                resp = client.get(url, params=params, timeout=timeout)
                ttfa = (time.perf_counter() - t0) * 1000
                ttfas.append(ttfa)
                errs: list[str] = []
                ctype = resp.headers.get("content-type", "").split(";")[0]
                dur = int(resp.headers.get("x-duration-ms") or 0)
                words = "-"
                if resp.status_code != 200:
                    errs.append(f"HTTP {resp.status_code}: {resp.text[:120]}")
                else:
                    if ctype not in AUDIO_TYPES:
                        errs.append(f"content-type {ctype!r}")
                    if dur <= 0:
                        errs.append(f"X-Duration-Ms {dur}")
                    try:
                        ts = json.loads(resp.headers.get("x-timestamps", ""))
                    except json.JSONDecodeError:
                        ts = None
                    words = str(len(ts)) if isinstance(ts, list) else "-"
                    errs += check_timestamps(ts, dur, seg["text"])
                head = client.head(url, params=params).status_code
                if head != 200:
                    errs.append(f"HEAD after GET: {head}")
                failures += bool(errs)
                print(
                    f"{name:34} {seg['id']:6d} {speed:5.2f} {pre:4d} {resp.status_code:4d} "
                    f"{ctype[:10]:10} {dur:7d} {words:>5} {len(resp.content):8d} {ttfa:8.0f} "
                    f"{head:4d}  {'ok' if not errs else 'FAIL'}"
                )
                for e in errs[:MAX_SHOWN_EXAMPLES]:
                    print(f"    {e}")
    print("-" * len(header))
    mean = sum(ttfas) / len(ttfas) if ttfas else 0.0
    print(
        f"audio: {n_req} requests, {failures} failures, "
        f"TTFA mean {mean:.0f} ms / max {max(ttfas, default=0.0):.0f} ms"
    )
    return failures


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--base-url", default="http://127.0.0.1:8765")
    ap.add_argument("--fixtures-dir", type=Path, default=DEFAULT_FIXTURES)
    ap.add_argument("--classes", default=DEFAULT_CLASSES, help="comma-separated manifest classes")
    ap.add_argument("--timeout", type=float, default=60.0, help="seconds to wait per document")
    ap.add_argument("--one", type=Path, metavar="PDF", help="upload one PDF, print 20 segments")
    ap.add_argument(
        "--user-docs",
        type=Path,
        nargs="?",
        const=DEFAULT_USER_DOCS,
        metavar="DIR",
        help=f"after the gate, upload every PDF in DIR (default {DEFAULT_USER_DOCS})",
    )
    ap.add_argument(
        "--audio",
        action="store_true",
        help="after the gate, fetch audio for the first 3 segments of each ready document",
    )
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
        code = run_gate(client, args.fixtures_dir, classes, args.timeout)
        if args.user_docs is not None:
            run_user_docs(client, args.user_docs, args.timeout)
        if args.audio and run_audio(client, max(args.timeout, 120.0)):
            code = 1
        return code


if __name__ == "__main__":
    sys.exit(main())
