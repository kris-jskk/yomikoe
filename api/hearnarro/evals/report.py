"""Markdown scorecard for a run record and for a compare result (D33)."""

from __future__ import annotations

from typing import Any


def _fmt(value: Any) -> str:
    return f"{value:.4f}" if isinstance(value, float) else str(value)


def _agg_rows(agg: dict[str, Any], prefix: str = "") -> list[tuple[str, Any]]:
    rows: list[tuple[str, Any]] = []
    for key, value in agg.items():
        if isinstance(value, dict):
            rows += _agg_rows(value, f"{prefix}{key}.")
        else:
            rows.append((f"{prefix}{key}", value))
    return rows


def scorecard(record: dict[str, Any], comparison: dict[str, Any] | None = None) -> str:
    """Aggregates and the worst example per suite; deltas and regressions when compared."""
    cfg = record["config"]
    lines = [
        f"# Eval run {record['run_id']}",
        "",
        (
            f"commit {record['commit']} · {record['date']} · backend {cfg['backend']} · "
            f"tesseract {cfg['tesseract']} · python {cfg['python']} · {record['seconds']} s"
        ),
    ]
    for sid, suite in record["suites"].items():
        deltas = comparison["suites"].get(sid, {}).get("aggregate", {}) if comparison else {}
        lines += ["", f"## {sid} {suite['title']} (tier {suite['tier']}, {suite['seconds']} s)"]
        lines += [
            "",
            f"{len(suite['examples'])} scored, {len(suite['skipped'])} skipped",
            "",
            "| aggregate | value | Δ |",
            "|---|---|---|",
        ]
        for key, value in _agg_rows(suite["aggregate"]):
            delta = f"{deltas[key]:+.4f}" if key in deltas else ""
            lines.append(f"| {key} | {_fmt(value)} | {delta} |")
        if suite["examples"]:
            pick = max if suite.get("direction") == "lower" else min
            worst = pick(suite["examples"], key=lambda e: e["score"])
            lines += ["", f"worst: {worst['id']} ({worst['class']}) {worst['score']:.4f}"]
    if comparison is not None:
        lines += lines_for_compare(comparison)
    return "\n".join(lines)


def lines_for_compare(comparison: dict[str, Any]) -> list[str]:
    """The regressions section of a compare result."""
    regs = comparison["regressions"]
    lines = ["", f"## Regressions vs {comparison['baseline']}: {len(regs)}"]
    for r in regs:
        detail = ", ".join(
            f"{m} {_fmt(v['baseline'])} → {_fmt(v['candidate'])}" for m, v in r["metrics"].items()
        )
        lines.append(
            f"- {r['suite']} {r['id']}: {r['reason']}" + (f" ({detail})" if detail else "")
        )
    return lines
