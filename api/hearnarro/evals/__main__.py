"""``python -m hearnarro.evals`` (D32).

``run <suite ...|all> [--tier N] [--out DIR] [--baseline RUN_ID]`` writes one run record and
prints the markdown scorecard (with deltas and regressions against the baseline if given);
``compare A B [--out DIR]`` prints the scorecard of B against A (run ids, paths or ``latest``).
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from hearnarro.evals import report, store


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m hearnarro.evals")
    sub = parser.add_subparsers(dest="command", required=True)
    p_run = sub.add_parser("run", help="run suites and write a record")
    p_run.add_argument("suites", nargs="+", help="suite ids (EVAL-1 ...) or 'all'")
    p_run.add_argument("--tier", type=int, default=0, help="highest tier for 'all' (default 0)")
    p_run.add_argument("--out", default=None, help="records directory (default evals/runs/)")
    p_run.add_argument("--baseline", default=None, help="run id to compare against")
    p_cmp = sub.add_parser("compare", help="compare two records")
    p_cmp.add_argument("a", help="baseline run id, path or 'latest'")
    p_cmp.add_argument("b", help="candidate run id, path or 'latest'")
    p_cmp.add_argument("--out", default=None, help="records directory (default evals/runs/)")
    args = parser.parse_args(argv)
    out_dir = Path(args.out) if args.out else store.DEFAULT_RUNS_DIR

    if args.command == "run":
        from hearnarro.evals.runner import run

        baseline = store.read_record(args.baseline, out_dir) if args.baseline else None
        record, path = run(args.suites, out_dir=out_dir, tier=args.tier)
        comparison = store.compare(baseline, record) if baseline else None
        print(report.scorecard(record, comparison))
        print(f"\nrecord: {path}")
        return 0

    a, b = store.read_record(args.a, out_dir), store.read_record(args.b, out_dir)
    print(report.scorecard(b, store.compare(a, b)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
