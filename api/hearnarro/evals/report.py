"""Markdown and HTML scorecards for a run record and a compare result (D31, D33)."""

from __future__ import annotations

import math
from html import escape
from typing import Any

from hearnarro.evals.store import compare


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


# --- HTML scorecard (E3; D31, D33) --------------------------------------------------------
#
# One page per run record, optionally against a baseline record. The output follows the
# Artifact page contract (no doctype/html/head/body unless ``standalone``) so it can be
# published unchanged; every colour is a theme token and every chart is drawn to scale from
# the record values.

# Headline aggregates per suite: (aggregate key, which way is better).
HEADLINES: dict[str, list[tuple[str, str]]] = {
    "EVAL-1": [("mean", "higher")],
    "EVAL-2": [("mean_f1", "higher")],
    "EVAL-3": [("total_mean_rate", "lower")],
    "EVAL-4": [("accuracy", "higher")],
    "EVAL-5": [("mean_wer", "lower")],
    "EVAL-6": [("share_within_150ms", "higher")],
    "EVAL-7": [("ttfa_p95_ms", "lower"), ("rtf_mean", "lower")],
}
MAX_BARS = 30
_NEUTRAL = 1e-9

_STYLE = """
/* Layout: a single reading column; summary tiles on top, one section per suite below. */
:root {
  --bg: #f6f7f8; --surface: #ffffff; --fg: #1b2228; --muted: #5d6973; --line: #d9dee3;
  --accent: #2f5f86; --tick: #1b2228;
  --good: #23764a; --good-bg: #e3f2e9; --bad: #b3261e; --bad-bg: #fbe7e5;
  --warn: #8a5a00; --warn-bg: #fbf0d9;
  --font-body: "Public Sans", system-ui, -apple-system, "Segoe UI", sans-serif;
  --font-data: "JetBrains Mono", ui-monospace, "SF Mono", Menlo, Consolas, monospace;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --bg: #12171b; --surface: #1a2026; --fg: #e2e7eb; --muted: #9aa6b0; --line: #2c353d;
    --accent: #6fa8d6; --tick: #e2e7eb;
    --good: #6cc28f; --good-bg: #183324; --bad: #f08a80; --bad-bg: #3a1c1a;
    --warn: #e0b25a; --warn-bg: #352a14; color-scheme: dark;
  }
}
:root[data-theme="dark"] {
  --bg: #12171b; --surface: #1a2026; --fg: #e2e7eb; --muted: #9aa6b0; --line: #2c353d;
  --accent: #6fa8d6; --tick: #e2e7eb;
  --good: #6cc28f; --good-bg: #183324; --bad: #f08a80; --bad-bg: #3a1c1a;
  --warn: #e0b25a; --warn-bg: #352a14; color-scheme: dark;
}
body { background: var(--bg); color: var(--fg); font-family: var(--font-body);
  font-size: 15px; line-height: 1.5; }
.page { max-width: 980px; margin: 0 auto;
  padding-left: max(16px, env(safe-area-inset-left, 0px));
  padding-right: max(16px, env(safe-area-inset-right, 0px)); padding-block: 28px 40px;
  display: grid; gap: 28px; }
h1, h2, h3 { text-wrap: balance; margin: 0; line-height: 1.2; }
h1 { font-size: 1.6rem; font-weight: 700; }
h2 { font-size: 1.2rem; font-weight: 650; }
h3 { font-size: 0.8rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.06em;
  color: var(--muted); }
p { margin: 0; }
code, .num, td, .meta dd { font-family: var(--font-data); font-variant-numeric: tabular-nums; }
code { font-size: 0.85em; overflow-wrap: anywhere; }
.meta { display: flex; flex-wrap: wrap; gap: 4px 20px; margin: 10px 0 0; font-size: 0.85rem; }
.meta div { display: flex; gap: 6px; min-width: 0; }
.meta dt { color: var(--muted); }
.meta dd { margin: 0; overflow-wrap: anywhere; }
.tiles { display: grid; grid-template-columns: repeat(auto-fill, minmax(min(100%, 180px), 1fr)); gap: 12px; }
.tile { background: var(--surface); border: 1px solid var(--line); border-radius: 6px;
  padding: 12px 14px; display: grid; gap: 4px; align-content: start; min-width: 0; }
.tile .sid { font-size: 0.75rem; letter-spacing: 0.06em; text-transform: uppercase;
  color: var(--muted); }
.tile .val { font-family: var(--font-data); font-variant-numeric: tabular-nums;
  font-size: 1.35rem; font-weight: 600; }
.tile .key { font-size: 0.78rem; color: var(--muted); }
.delta { font-family: var(--font-data); font-variant-numeric: tabular-nums; font-size: 0.85rem; }
.delta.good { color: var(--good); } .delta.bad { color: var(--bad); }
.delta.flat { color: var(--muted); }
.badge { justify-self: start; font-size: 0.75rem; padding: 1px 8px; border-radius: 999px;
  border: 1px solid currentColor; }
.badge.none { color: var(--muted); }
.badge.ok { color: var(--good); background: var(--good-bg); }
.badge.reg { color: var(--bad); background: var(--bad-bg); }
section.suite { display: grid; gap: 14px; border-top: 1px solid var(--line); padding-top: 20px; }
.suite-head { display: flex; flex-wrap: wrap; align-items: baseline; gap: 6px 14px; }
.suite-head .sub { color: var(--muted); font-size: 0.85rem; }
.scroll { overflow-x: auto; max-width: 100%; }
table { border-collapse: collapse; font-size: 0.82rem; min-width: 100%; }
th, td { text-align: right; padding: 4px 10px; border-bottom: 1px solid var(--line);
  white-space: nowrap; }
th:first-child, td:first-child { text-align: left; }
th { font-weight: 600; color: var(--muted); font-size: 0.75rem; letter-spacing: 0.04em; }
svg.bars { display: block; width: 100%; max-width: 100%; height: auto; }
svg.bars text { fill: var(--fg); font-family: var(--font-data); }
svg.bars .axis text { fill: var(--muted); }
svg.bars .grid { stroke: var(--line); stroke-width: 1; }
svg.bars .bar { fill: var(--accent); }
svg.bars .bar.reg { fill: var(--bad); }
svg.bars .base { stroke: var(--tick); stroke-width: 2; }
.caption { font-size: 0.82rem; color: var(--muted); max-width: 70ch; }
ol.regressions { margin: 0; padding-left: 1.4em; display: grid; gap: 2px; font-size: 0.85rem; }
ol.regressions .delta { color: var(--bad); }
.noreg { font-size: 0.85rem; color: var(--good); }
.worst { background: var(--surface); border: 1px solid var(--line); border-radius: 6px;
  padding: 12px 14px; display: grid; gap: 8px; min-width: 0; }
.worst dl { margin: 0; display: grid; grid-template-columns: minmax(90px, max-content) 1fr;
  gap: 2px 14px; font-size: 0.82rem; }
.worst dt { color: var(--muted); font-family: var(--font-data); }
.worst dd { margin: 0; font-family: var(--font-data); overflow-wrap: anywhere; min-width: 0; }
footer { border-top: 1px solid var(--line); padding-top: 14px; font-size: 0.82rem;
  color: var(--muted); display: grid; gap: 4px; }
"""

_FONTS = (
    '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Public+Sans:'
    'wght@400;600;700&family=JetBrains+Mono:wght@400;600&display=swap">'
)


def fmt_num(value: Any) -> str:
    """Scorecard number format: 4 decimals below 100, 1 decimal from 100 up."""
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return f"{value:.1f}" if abs(value) >= 100 else f"{value:.4f}"
    return str(value)


def fmt_delta(value: float, ref: float) -> str:
    return f"{value:+.1f}" if abs(ref) >= 100 else f"{value:+.4f}"


def _e(value: Any) -> str:
    return escape(str(value), quote=True)


def _numeric_rows(agg: dict[str, Any]) -> list[tuple[str, float]]:
    return [
        (k, v) for k, v in _agg_rows(agg) if isinstance(v, int | float) and not isinstance(v, bool)
    ]


def _lookup(agg: dict[str, Any], key: str) -> float | None:
    return dict(_numeric_rows(agg)).get(key)


def _delta_class(delta: float, better: str) -> str:
    if abs(delta) < _NEUTRAL:
        return "flat"
    return "good" if (delta > 0) == (better == "higher") else "bad"


def _tile(sid: str, suite: dict[str, Any], base: dict[str, Any] | None, n_regs: int) -> str:
    parts = [f'<span class="sid">{_e(sid)} · {_e(suite["title"])}</span>']
    for key, better in HEADLINES.get(sid, []):
        value = _lookup(suite["aggregate"], key)
        if value is None:
            continue
        parts.append(f'<span class="val">{fmt_num(value)}</span>')
        parts.append(f'<span class="key">{_e(key)} ({better} is better)</span>')
        old = _lookup(base["aggregate"], key) if base else None
        if old is not None:
            delta = value - old
            cls = _delta_class(delta, better)
            parts.append(
                f'<span class="delta {cls}">{fmt_delta(delta, value)} vs {fmt_num(old)}</span>'
            )
    if base is None:
        parts.append('<span class="badge none">no baseline</span>')
    elif n_regs:
        parts.append(f'<span class="badge reg">{n_regs} regression{"s" * (n_regs != 1)}</span>')
    else:
        parts.append('<span class="badge ok">0 regressions</span>')
    return f'<div class="tile" data-suite="{_e(sid)}">' + "".join(parts) + "</div>"


def _agg_table(suite: dict[str, Any], base: dict[str, Any] | None) -> str:
    base_rows = dict(_numeric_rows(base["aggregate"])) if base else {}
    rows = []
    for key, value in _numeric_rows(suite["aggregate"]):
        old = base_rows.get(key)
        b = fmt_num(old) if old is not None else "–"
        d = fmt_delta(value - old, value) if old is not None else "–"
        rows.append(f"<tr><td>{_e(key)}</td><td>{b}</td><td>{fmt_num(value)}</td><td>{d}</td></tr>")
    head = "<tr><th>aggregate</th><th>baseline</th><th>this run</th><th>Δ</th></tr>"
    return f'<div class="scroll"><table>{head}{"".join(rows)}</table></div>'


def _nice_max(value: float) -> float:
    if value <= 0:
        return 1.0
    if value <= 1.0:
        return 1.0
    mag = 10 ** math.floor(math.log10(value))
    for step in (1, 2, 2.5, 5, 10):
        if value <= step * mag:
            return step * mag
    return 10 * mag


def _short(text: str, limit: int = 46) -> str:
    return text if len(text) <= limit else text[: limit - 17] + "…" + text[-16:]


def _bars(
    sid: str,
    suite: dict[str, Any],
    base: dict[str, Any] | None,
    regressed: set[str],
) -> str:
    lower = suite.get("direction") == "lower"
    examples = sorted(suite["examples"], key=lambda e: e["score"], reverse=lower)
    shown, rest = examples[:MAX_BARS], len(examples) - MAX_BARS
    base_scores = {e["id"]: e["score"] for e in base["examples"]} if base else {}
    top = max([e["score"] for e in shown] + [base_scores.get(e["id"], 0.0) for e in shown])
    x_max = _nice_max(top)
    label_w, plot_w, row_h, pad_top = 300, 380, 18, 8
    width = label_w + plot_w + 70
    height = pad_top + row_h * len(shown) + 30

    def x(v: float) -> float:
        return label_w + plot_w * max(v, 0.0) / x_max

    svg_open = (
        f'<svg class="bars" viewBox="0 0 {width} {height}" role="img" '
        f'aria-label="{_e(sid)} per-example scores, worst first">'
    )
    out = [svg_open]
    axis_y = pad_top + row_h * len(shown) + 4
    out.append('<g class="axis">')
    for i in range(5):
        tv = x_max * i / 4
        tx = x(tv)
        out.append(
            f'<line class="grid" x1="{tx:.1f}" y1="{pad_top - 4}" x2="{tx:.1f}" y2="{axis_y}"/>'
        )
        out.append(
            f'<text x="{tx:.1f}" y="{axis_y + 14}" font-size="11" '
            f'text-anchor="middle">{tv:g}</text>'
        )
    out.append("</g>")
    for i, ex in enumerate(shown):
        y = pad_top + i * row_h
        cls = "bar reg" if ex["id"] in regressed else "bar"
        tip = f"{ex['id']}: {fmt_num(ex['score'])}"
        old = base_scores.get(ex["id"])
        if old is not None:
            tip += f" (baseline {fmt_num(old)})"
        bw = max(x(ex["score"]) - label_w, 1.0)
        out.append(f"<g><title>{_e(tip)}</title>")
        out.append(
            f'<text x="{label_w - 8}" y="{y + 12.5}" font-size="11" '
            f'text-anchor="end">{_e(_short(ex["id"]))}</text>'
        )
        out.append(
            f'<rect class="{cls}" x="{label_w}" y="{y + 3}" width="{bw:.1f}" '
            f'height="{row_h - 6}" rx="2"/>'
        )
        if old is not None:
            bx = x(old)
            out.append(
                f'<line class="base" x1="{bx:.1f}" y1="{y + 1}" x2="{bx:.1f}" y2="{y + row_h - 1}"/>'
            )
        out.append(
            f'<text x="{x(ex["score"]) + 6:.1f}" y="{y + 12.5}" font-size="11">'
            f"{fmt_num(ex['score'])}</text></g>"
        )
    out.append("</svg>")
    more = f" and {rest} more not drawn." if rest > 0 else "."
    tick = " The dark tick marks the baseline score of the same example." if base_scores else ""
    red = " Red bars are regressions." if regressed else ""
    caption = (
        f'<p class="caption">Per-example score ({"lower" if lower else "higher"} is better), '
        f"worst first, axis 0 to {fmt_num(float(x_max))}; {len(shown)} of {len(examples)} "
        f"examples drawn{more}{tick}{red}</p>"
    )
    return '<div class="scroll">' + "".join(out) + "</div>" + caption


def _regressions(sid: str, regs: list[dict[str, Any]], has_base: bool) -> str:
    if not has_base:
        return '<p class="caption">no baseline for this suite; nothing to compare.</p>'
    if not regs:
        return '<p class="noreg">0 regressions against the baseline.</p>'
    items = []
    for r in regs:
        if r["reason"] == "missing":
            items.append(f"<li><code>{_e(r['id'])}</code> missing from this run</li>")
            continue
        parts = []
        for metric, v in r["metrics"].items():
            if v["delta"] is None:
                parts.append(f"{_e(metric)} {fmt_num(v['baseline'])} → {fmt_num(v['candidate'])}")
            else:
                parts.append(
                    f"{_e(metric)} {fmt_num(v['baseline'])} → {fmt_num(v['candidate'])} "
                    f'<span class="delta">{fmt_delta(v["delta"], v["baseline"])}</span>'
                )
        items.append(f"<li><code>{_e(r['id'])}</code> {'; '.join(parts)}</li>")
    return (
        f"<h3>Regressions ({len(regs)})</h3>"
        f'<ol class="regressions" data-suite="{_e(sid)}">{"".join(items)}</ol>'
    )


def _detail_rows(example: dict[str, Any], prefix: str = "") -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for key, value in example.items():
        if isinstance(value, dict):
            rows += [
                (k, v)
                for k, v in _detail_rows(value, f"{prefix}{key}.")
                if v not in ("0", "0.0000")
            ]
        elif isinstance(value, list):
            rows.append((f"{prefix}{key}", ", ".join(fmt_num(v) for v in value)))
        else:
            rows.append((f"{prefix}{key}", fmt_num(value)))
    return rows


def _worst(suite: dict[str, Any]) -> str:
    if not suite["examples"]:
        return ""
    pick = max if suite.get("direction") == "lower" else min
    worst = pick(suite["examples"], key=lambda e: e["score"])
    rows = "".join(f"<dt>{_e(k)}</dt><dd>{_e(v)}</dd>" for k, v in _detail_rows(worst))
    return (
        f'<div class="worst"><h3>Worst example</h3><dl>{rows}</dl>'
        '<p class="caption">Zero-valued nested checks are omitted.</p></div>'
    )


def _parts(record: dict[str, Any], baseline: dict[str, Any] | None) -> tuple[str, str]:
    comparison = compare(baseline, record) if baseline else None
    regs_by: dict[str, list[dict[str, Any]]] = {}
    for r in comparison["regressions"] if comparison else []:
        regs_by.setdefault(r["suite"], []).append(r)
    title = "HearNarro Eval Scorecard"
    head = (
        f"<title>{title}</title>\n"
        '<meta name="claude:viewport-fit-sides" content="cover">\n'
        f"<style>{_STYLE}</style>\n{_FONTS}\n"
    )
    cfg = record["config"]
    meta = [
        ("run", record["run_id"]),
        ("commit", record["commit"]),
        ("date", record["date"]),
        ("backend", cfg.get("backend")),
        ("tesseract", cfg.get("tesseract")),
        ("python", cfg.get("python")),
        ("tier", cfg.get("tier")),
        ("wall", f"{record['seconds']} s"),
        ("baseline", baseline["run_id"] if baseline else "none"),
    ]
    meta_html = "".join(f"<div><dt>{k}</dt><dd>{_e(fmt_num(v))}</dd></div>" for k, v in meta)
    tiles, sections = [], []
    for sid, suite in record["suites"].items():
        base = baseline["suites"].get(sid) if baseline else None
        regs = regs_by.get(sid, [])
        tiles.append(_tile(sid, suite, base, len(regs)))
        regressed = {r["id"] for r in regs}
        sub = (
            f"tier {suite['tier']} · {len(suite['examples'])} scored · "
            f"{len(suite['skipped'])} skipped · {suite['seconds']} s"
        )
        sections.append(
            f'<section class="suite" id="{_e(sid)}"><div class="suite-head">'
            f'<h2>{_e(sid)} {_e(suite["title"])}</h2><span class="sub">{sub}</span></div>'
            f"{_agg_table(suite, base)}{_bars(sid, suite, base, regressed)}"
            f"{_regressions(sid, regs, base is not None)}{_worst(suite)}</section>"
        )
    n_regs = len(comparison["regressions"]) if comparison else 0
    against = f" against {_e(baseline['run_id'])}: {n_regs} regressions" if baseline else ""
    base_arg = f" --baseline {_e(baseline['run_id'])}" if baseline else ""
    body = (
        '<main class="page"><header><h1>HearNarro Eval Scorecard</h1>'
        f'<dl class="meta">{meta_html}</dl></header>'
        f'<p class="caption">One tile per suite: the headline aggregate, its change against '
        f"the baseline, and the count of examples that regressed (D33){against}. Evals are the "
        "trend line; the gate tests remain the only merge blocker.</p>"
        f'<div class="tiles">{"".join(tiles)}</div>{"".join(sections)}'
        "<footer><p>Reproduce from <code>api/</code>:</p>"
        f"<p><code>python -m hearnarro.evals run all --tier {_e(cfg.get('tier', 0))}</code></p>"
        f"<p><code>python -m hearnarro.evals report {_e(record['run_id'])}{base_arg} "
        "--html &lt;path&gt;</code></p></footer></main>"
    )
    return head, body


def html_scorecard(
    record: dict[str, Any], baseline: dict[str, Any] | None = None, standalone: bool = False
) -> str:
    """The HTML scorecard of ``record`` (optionally against ``baseline``).

    By default the page follows the Artifact contract (``<title>`` first, no document
    skeleton); ``standalone`` wraps it in doctype/html/head/body for opening locally.
    """
    head, body = _parts(record, baseline)
    if not standalone:
        return head + body + "\n"
    return (
        '<!doctype html>\n<html lang="en"><head><meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
        f"{head}</head><body>{body}</body></html>\n"
    )
