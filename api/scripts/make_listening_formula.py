"""Write ``yomikoe/evals/data/listening_formula_10.jsonl``: the EVAL-9 formula sentence set (MATH-1..4).

One row per formula fixture: the ``normalized_text`` (what the voice is given) of the first equation-type
segment with at least ``MIN_WORDS`` spoken words; the fallback (scanned or no such segment) is the first
body segment carrying maths spans (math_json). Each row records fixture, segment order and the raw page text.
Deterministic. Run from api/: ``python scripts/make_listening_formula.py``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from yomikoe.evals.suites import _fixtures
from yomikoe.evals.suites import eval10_mathspeak as eval10

MIN_WORDS = 8
OUT = (
    Path(__file__).resolve().parents[1]
    / "yomikoe"
    / "evals"
    / "data"
    / "listening_formula_10.jsonl"
)


def pick(result: Any) -> tuple[Any, str]:
    """(segment, rule) for one ingest result."""
    by_id = {b.id: b for b in result.blocks}
    for s in result.segments:
        if by_id[s.block_id].type == "equation" and len(s.normalized_text.split()) >= MIN_WORDS:
            return s, "equation"
    for s in result.segments:
        if by_id[s.block_id].type != "equation" and getattr(s, "math_json", None):
            return s, "fallback_body_math"
    raise LookupError("no maths segment")


def build() -> list[dict[str, Any]]:
    rows = []
    for n, entry in enumerate(eval10.formula_entries(), start=1):
        seg, rule = pick(_fixtures.ingest_result(entry["name"]))
        rows.append(
            {
                "id": f"formula_{n:02d}",
                "fixture": entry["name"],
                "segment_order": seg.order,
                "rule": rule,
                "text": " ".join(seg.normalized_text.split()),
                "source_text": seg.text,
            }
        )
    return rows


def main() -> int:
    rows = build()
    OUT.write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8"
    )
    print(f"wrote {len(rows)} rows to {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
