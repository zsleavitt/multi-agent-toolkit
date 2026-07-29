#!/usr/bin/env python3
"""CLI runner for the MAT agent-quality eval harness.

Example::

    python3 evals/run_evals.py
    python3 evals/run_evals.py --write-baseline
    python3 evals/run_evals.py --llm-judge --threshold 0.9
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Allow running as a script from repo root without install.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from evals.harness.execute import execute_task
from evals.harness.loader import baseline_path, load_tasks
from evals.harness.report import (
    compare_to_baseline,
    format_markdown_summary,
    load_baseline,
    summarize,
    write_baseline,
)
from evals.harness.score import score_task


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run MAT agent-quality evals")
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.9,
        help="Minimum aggregate pass rate (default: 0.9)",
    )
    parser.add_argument(
        "--llm-judge",
        action="store_true",
        help="Enable optional heuristic LLM-as-judge checks (off in CI)",
    )
    parser.add_argument(
        "--write-baseline",
        action="store_true",
        help="Overwrite evals/baseline.json from this run",
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        default=None,
        help="Path to baseline JSON (default: evals/baseline.json)",
    )
    parser.add_argument(
        "--json-out",
        type=Path,
        default=None,
        help="Write full structured report JSON to this path",
    )
    parser.add_argument(
        "--markdown-out",
        type=Path,
        default=None,
        help="Write markdown summary to this path (for PR comments)",
    )
    parser.add_argument(
        "--tags",
        nargs="*",
        default=None,
        help="Only run tasks matching any of these tags",
    )
    parser.add_argument(
        "--ids",
        nargs="*",
        default=None,
        help="Only run these task ids",
    )
    args = parser.parse_args(argv)

    tasks = load_tasks(tags=args.tags, task_ids=args.ids)
    if not tasks:
        print("No eval tasks found.", file=sys.stderr)
        return 2

    results = []
    for task in tasks:
        execution = execute_task(task)
        results.append(score_task(execution, llm_judge=args.llm_judge))

    report = summarize(results, threshold=args.threshold)
    base_path = args.baseline or baseline_path()
    baseline = load_baseline(base_path)
    comparison = compare_to_baseline(report, baseline)

    if args.write_baseline:
        write_baseline(report, base_path)
        print(f"Wrote baseline → {base_path}")

    payload = report.to_dict()
    payload["comparison"] = comparison

    if args.json_out:
        args.json_out.write_text(
            json.dumps(payload, indent=2) + "\n", encoding="utf-8"
        )

    md = format_markdown_summary(report, comparison)
    if args.markdown_out:
        args.markdown_out.write_text(md, encoding="utf-8")
    print(md)

    for result in results:
        status = "PASS" if result.passed else "FAIL"
        print(f"  [{status}] {result.task_id} score={result.score}")

    if not report.gate_ok:
        return 1
    if comparison.get("regressions"):
        # Soft signal: still fail CI if pass-rate ok but tasks regressed vs baseline
        # only when pass rate also dropped or must_pass failed (already covered).
        # Flag score regressions in output; gate remains pass_rate + must_pass.
        print(
            f"Note: {len(comparison['regressions'])} regression(s) vs baseline "
            "(informational unless pass rate/must_pass gate failed)."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
