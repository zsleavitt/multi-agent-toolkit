"""Aggregate reports and baseline comparison."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from evals.harness.score import ScoreResult


@dataclass
class EvalReport:
    pass_rate: float
    total: int
    passed: int
    failed: int
    must_pass_failures: list[str] = field(default_factory=list)
    results: list[ScoreResult] = field(default_factory=list)
    threshold: float = 0.9

    @property
    def gate_ok(self) -> bool:
        if self.must_pass_failures:
            return False
        if self.total == 0:
            return False
        return self.pass_rate + 1e-9 >= self.threshold

    def to_dict(self) -> dict[str, Any]:
        return {
            "pass_rate": self.pass_rate,
            "total": self.total,
            "passed": self.passed,
            "failed": self.failed,
            "must_pass_failures": list(self.must_pass_failures),
            "threshold": self.threshold,
            "gate_ok": self.gate_ok,
            "results": [
                {
                    "task_id": r.task_id,
                    "passed": r.passed,
                    "score": r.score,
                    "must_pass": r.must_pass,
                    "reasons": list(r.reasons),
                    "tags": list(r.tags),
                    "checks": [asdict(c) for c in r.checks],
                }
                for r in self.results
            ],
        }


def summarize(
    results: list[ScoreResult],
    *,
    threshold: float = 0.9,
) -> EvalReport:
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    failed = total - passed
    pass_rate = (passed / total) if total else 0.0
    must_pass_failures = [r.task_id for r in results if r.must_pass and not r.passed]
    return EvalReport(
        pass_rate=round(pass_rate, 4),
        total=total,
        passed=passed,
        failed=failed,
        must_pass_failures=must_pass_failures,
        results=results,
        threshold=threshold,
    )


def write_baseline(report: EvalReport, path: Path) -> None:
    payload = {
        "schema_version": "1.0.0",
        "pass_rate": report.pass_rate,
        "total": report.total,
        "passed": report.passed,
        "failed": report.failed,
        "tasks": {
            r.task_id: {"passed": r.passed, "score": r.score}
            for r in report.results
        },
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def load_baseline(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def compare_to_baseline(
    report: EvalReport,
    baseline: dict[str, Any] | None,
) -> dict[str, Any]:
    """Compute pass-rate and per-task score deltas vs a committed baseline."""
    if not baseline:
        return {
            "baseline_present": False,
            "pass_rate_delta": None,
            "regressions": [],
            "improvements": [],
        }

    base_rate = float(baseline.get("pass_rate") or 0.0)
    delta = round(report.pass_rate - base_rate, 4)
    base_tasks = baseline.get("tasks") or {}
    regressions: list[dict[str, Any]] = []
    improvements: list[dict[str, Any]] = []

    for result in report.results:
        prior = base_tasks.get(result.task_id) or {}
        prior_score = float(prior.get("score") or 0.0)
        prior_passed = bool(prior.get("passed", False))
        score_delta = round(result.score - prior_score, 4)
        if prior_passed and not result.passed:
            regressions.append(
                {
                    "task_id": result.task_id,
                    "score_delta": score_delta,
                    "reason": "was passing, now failing",
                }
            )
        elif result.score + 1e-9 < prior_score:
            regressions.append(
                {
                    "task_id": result.task_id,
                    "score_delta": score_delta,
                    "reason": "score dropped",
                }
            )
        elif (not prior_passed and result.passed) or result.score > prior_score + 1e-9:
            improvements.append(
                {
                    "task_id": result.task_id,
                    "score_delta": score_delta,
                }
            )

    return {
        "baseline_present": True,
        "baseline_pass_rate": base_rate,
        "pass_rate_delta": delta,
        "regressions": regressions,
        "improvements": improvements,
    }


def format_markdown_summary(
    report: EvalReport,
    comparison: dict[str, Any] | None = None,
) -> str:
    lines = [
        "## MAT Eval Gate",
        "",
        f"- Pass rate: **{report.pass_rate:.1%}** ({report.passed}/{report.total})",
        f"- Threshold: {report.threshold:.0%}",
        f"- Gate: {'PASS' if report.gate_ok else 'FAIL'}",
    ]
    if report.must_pass_failures:
        lines.append(
            f"- must_pass failures: {', '.join(report.must_pass_failures)}"
        )
    if comparison and comparison.get("baseline_present"):
        delta = comparison.get("pass_rate_delta")
        lines.append(f"- Pass rate Δ vs baseline: {delta:+.1%}" if delta is not None else "")
        regs = comparison.get("regressions") or []
        if regs:
            lines.append(f"- Regressions: {len(regs)}")
            for reg in regs[:10]:
                lines.append(f"  - `{reg['task_id']}`: {reg['reason']}")
    failed = [r for r in report.results if not r.passed]
    if failed:
        lines.append("")
        lines.append("### Failures")
        for r in failed:
            reason = "; ".join(r.reasons) if r.reasons else "failed"
            lines.append(f"- `{r.task_id}`: {reason}")
    lines.append("")
    return "\n".join(lines)
