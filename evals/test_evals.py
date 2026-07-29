"""Pytest CI gate for the MAT agent-quality eval harness.

Primary gate (used by ``.github/workflows/eval.yml``)::

    python -m pytest evals/ -q

Never calls live CLIs — mock adapters only.
"""

from __future__ import annotations

import json
import os
import warnings
from pathlib import Path

import pytest

from evals.harness.execute import execute_task
from evals.harness.loader import baseline_path, load_tasks
from evals.harness.report import compare_to_baseline, load_baseline, summarize
from evals.harness.score import score_task

TASKS = load_tasks()
THRESHOLD = float(os.environ.get("EVAL_PASS_THRESHOLD", "0.9"))


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    if "eval_task" in metafunc.fixturenames:
        metafunc.parametrize(
            "eval_task",
            TASKS,
            ids=[t.id for t in TASKS],
        )


@pytest.fixture(scope="session")
def scored_results():
    """Run the full suite once per session for aggregate gating."""
    results = []
    for task in TASKS:
        execution = execute_task(task)
        results.append(score_task(execution, llm_judge=False))
    return results


def test_eval_task(eval_task, scored_results):
    """Per-task checks — only ``must_pass`` tasks hard-fail individually.

    Soft failures still count against the aggregate pass-rate gate.
    """
    result = next(r for r in scored_results if r.task_id == eval_task.id)
    if result.passed:
        return
    detail = "; ".join(result.reasons) or "failed"
    if eval_task.must_pass:
        pytest.fail(f"must_pass task failed: {eval_task.id}: {detail}")
    warnings.warn(f"eval soft-fail: {eval_task.id}: {detail}", UserWarning, stacklevel=1)


def test_aggregate_pass_rate_gate(scored_results, tmp_path: Path):
    """Fail when aggregate pass rate drops below threshold or must_pass fails."""
    assert TASKS, "No golden tasks loaded from evals/tasks/"
    report = summarize(scored_results, threshold=THRESHOLD)
    baseline = load_baseline(baseline_path())
    comparison = compare_to_baseline(report, baseline)

    # Persist artifacts for the workflow summary step when present.
    out_dir = Path(os.environ.get("EVAL_ARTIFACT_DIR", str(tmp_path)))
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "eval-report.json").write_text(
        json.dumps({**report.to_dict(), "comparison": comparison}, indent=2) + "\n",
        encoding="utf-8",
    )

    if report.must_pass_failures:
        pytest.fail(
            "must_pass failures: " + ", ".join(report.must_pass_failures)
        )
    if report.pass_rate + 1e-9 < THRESHOLD:
        pytest.fail(
            f"pass rate {report.pass_rate:.1%} below threshold {THRESHOLD:.0%}"
        )
    if comparison.get("baseline_present") and comparison.get("pass_rate_delta") is not None:
        delta = comparison["pass_rate_delta"]
        # Flag regressions that drop below baseline by more than 1pp while still
        # above the absolute threshold — surfaces silent drift in CI logs.
        if delta < -0.01:
            pytest.fail(
                f"pass rate regressed vs baseline by {delta:+.1%} "
                f"(current={report.pass_rate:.1%}, "
                f"baseline={comparison.get('baseline_pass_rate'):.1%})"
            )
