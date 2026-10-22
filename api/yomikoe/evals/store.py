"""Run-record store and compare (D32, D33).

Records are JSON files ``<out_dir>/<run_id>.json`` with ``run_id = <YYYY-MM-DD>_<shortsha>``;
``latest.json`` in the same directory names the newest record (a small JSON pointer rather
than a symlink, so it survives checkouts on every platform).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# The repo-root evals/runs/ (api/yomikoe/evals/store.py -> parents[3] is the repo root).
DEFAULT_RUNS_DIR = Path(__file__).resolve().parents[3] / "evals" / "runs"
LATEST = "latest.json"
# D33: an example regresses when a 0..1 score falls by more than this (per suite); EVAL-3 is
# junk per 1 000 words (lower is better), so a rise of more than 1 is a regression there.
TOLERANCE: dict[str, float] = {
    "EVAL-1": 0.01,
    "EVAL-2": 0.01,
    "EVAL-3": 1.0,
    "EVAL-4": 0.01,
    "EVAL-5": 0.01,  # WER, 0..1
}
DEFAULT_TOLERANCE = 0.01
_EPS = 1e-9


def write_record(record: dict[str, Any], out_dir: Path) -> Path:
    """Write ``record`` as ``<run_id>.json`` and point ``latest.json`` at it."""
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{record['run_id']}.json"
    path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n")
    pointer = {"run_id": record["run_id"], "file": path.name}
    (out_dir / LATEST).write_text(json.dumps(pointer, indent=2) + "\n")
    return path


def read_record(ref: str, out_dir: Path = DEFAULT_RUNS_DIR) -> dict[str, Any]:
    """Load a record by file path, run id, or ``latest`` (resolved in ``out_dir``)."""
    path = Path(ref)
    if not path.is_file():
        if ref == "latest":
            ref = json.loads((out_dir / LATEST).read_text())["run_id"]
        path = out_dir / f"{ref}.json"
    return json.loads(path.read_text())


def _is_number(value: Any) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)


def _flatten(agg: dict[str, Any], prefix: str = "") -> dict[str, float]:
    out: dict[str, float] = {}
    for key, value in agg.items():
        if isinstance(value, dict):
            out.update(_flatten(value, f"{prefix}{key}."))
        elif _is_number(value):
            out[f"{prefix}{key}"] = value
    return out


def _bools(example: dict[str, Any]) -> dict[str, bool]:
    return {k: v for k, v in example.items() if isinstance(v, bool)}


def _rule(sid: str, metric: str, sign: float, tol: float) -> tuple[float, float, bool] | None:
    """(sign, tolerance, relative) for one example metric; None when it is not compared.
    Suite modules override the suite default with ``METRIC_RULES`` (D33)."""
    from yomikoe.evals.suites import SUITES

    rules = getattr(SUITES.get(sid), "METRIC_RULES", {})
    if metric not in rules:
        return sign, tol, False
    way, m_tol, relative = rules[metric]
    if way == "none":
        return None
    return (-1.0 if way == "lower" else 1.0), m_tol, relative


def compare(baseline: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    """Deltas (candidate - baseline) per suite and the regressions list (D33).

    Returns ``{"baseline", "candidate", "suites": {id: {"aggregate": {key: delta},
    "examples": {example_id: {metric: delta}}}}, "regressions": [...]}``. A regression is one
    entry per example: a numeric metric fell by more than the suite tolerance, a boolean check
    went from true to false, or the example is missing from the candidate ("new failure").
    A suite whose record (or registry entry) says ``direction: "lower"`` regresses when a
    metric rises by more than the tolerance instead. Nested example metrics (EVAL-3's
    ``checks.<name>.rate``) are compared under dotted keys.
    """
    from yomikoe.evals.suites import direction

    suites: dict[str, Any] = {}
    regressions: list[dict[str, Any]] = []
    for sid, base in baseline["suites"].items():
        cand = candidate["suites"].get(sid)
        if cand is None:
            continue
        tol = TOLERANCE.get(sid, DEFAULT_TOLERANCE)
        sign = -1.0 if base.get("direction", direction(sid)) == "lower" else 1.0
        base_agg, cand_agg = _flatten(base["aggregate"]), _flatten(cand["aggregate"])
        agg_delta = {k: cand_agg[k] - v for k, v in base_agg.items() if k in cand_agg}
        cand_ex = {e["id"]: e for e in cand["examples"]}
        ex_delta: dict[str, dict[str, float]] = {}
        for ex in base["examples"]:
            other = cand_ex.get(ex["id"])
            if other is None:
                regressions.append(
                    {"suite": sid, "id": ex["id"], "reason": "missing", "metrics": {}}
                )
                continue
            deltas: dict[str, float] = {}
            fell: dict[str, dict[str, Any]] = {}
            flat_new = _flatten(other)
            for metric, value in {**_flatten(ex), **_bools(ex)}.items():
                new = flat_new.get(metric, other.get(metric))
                rule = _rule(sid, metric, sign, tol)
                if _is_number(value) and _is_number(new):
                    deltas[metric] = new - value
                    if rule is None:
                        continue
                    m_sign, m_tol, relative = rule
                    limit = m_tol * abs(value) if relative else m_tol
                    if m_sign * (new - value) < -limit - _EPS:
                        fell[metric] = {"baseline": value, "candidate": new, "delta": new - value}
                elif value is True and new is False:
                    fell[metric] = {"baseline": True, "candidate": False, "delta": None}
            ex_delta[ex["id"]] = deltas
            if fell:
                regressions.append(
                    {"suite": sid, "id": ex["id"], "reason": "score fell", "metrics": fell}
                )
        suites[sid] = {"aggregate": agg_delta, "examples": ex_delta}
    return {
        "baseline": baseline["run_id"],
        "candidate": candidate["run_id"],
        "suites": suites,
        "regressions": regressions,
    }
