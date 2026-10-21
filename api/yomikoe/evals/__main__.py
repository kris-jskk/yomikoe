"""``python -m yomikoe.evals`` (D32).

``run <suite ...|all> [--tier N] [--out DIR] [--baseline RUN_ID]`` writes one run record and
prints the markdown scorecard (with deltas and regressions against the baseline if given);
``compare A B [--out DIR]`` prints the scorecard of B against A (run ids, paths or ``latest``);
``report RUN [--baseline RUN] [--html PATH] [--standalone] [--out DIR]`` writes the HTML
scorecard (E3) to PATH, or prints the markdown scorecard when ``--html`` is not given; ``listening prepare|ingest`` (E4, EVAL-9) prepares and
records listening sessions.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from yomikoe.evals import listening, report, store


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m yomikoe.evals")
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
    p_rep = sub.add_parser("report", help="render the scorecard of one record")
    p_rep.add_argument("run", help="run id, path or 'latest'")
    p_rep.add_argument("--baseline", default=None, help="baseline run id, path or 'latest'")
    p_rep.add_argument("--html", default=None, help="write the HTML scorecard to this path")
    p_rep.add_argument(
        "--standalone", action="store_true", help="wrap the HTML in a full document skeleton"
    )
    p_rep.add_argument("--out", default=None, help="records directory (default evals/runs/)")
    listening.register(sub)
    args = parser.parse_args(argv)
    if args.command == "listening":
        return listening.run_verb(args)
    out_dir = Path(args.out) if args.out else store.DEFAULT_RUNS_DIR

    if args.command == "run":
        from yomikoe.evals.runner import run

        baseline = store.read_record(args.baseline, out_dir) if args.baseline else None
        record, path = run(args.suites, out_dir=out_dir, tier=args.tier)
        comparison = store.compare(baseline, record) if baseline else None
        print(report.scorecard(record, comparison))
        print(f"\nrecord: {path}")
        return 0

    if args.command == "report":
        record = store.read_record(args.run, out_dir)
        base = store.read_record(args.baseline, out_dir) if args.baseline else None
        if args.html is None:
            print(report.scorecard(record, store.compare(base, record) if base else None))
            return 0
        html_path = Path(args.html)
        html_path.parent.mkdir(parents=True, exist_ok=True)
        html_path.write_text(report.html_scorecard(record, base, standalone=args.standalone))
        n_regs = len(store.compare(base, record)["regressions"]) if base else 0
        against = f" against {base['run_id']} ({n_regs} regressions)" if base else ""
        print(f"scorecard {record['run_id']}{against}: {html_path}")
        return 0

    a, b = store.read_record(args.a, out_dir), store.read_record(args.b, out_dir)
    print(report.scorecard(b, store.compare(a, b)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
