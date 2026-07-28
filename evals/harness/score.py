"""Deterministic scoring for eval trajectories (+ optional LLM judge)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from evals.harness.execute import TaskExecution
from evals.harness.llm_judge import judge_output


@dataclass
class CheckResult:
    name: str
    passed: bool
    expected: Any
    actual: Any
    detail: str = ""


@dataclass
class ScoreResult:
    task_id: str
    passed: bool
    score: float
    must_pass: bool
    reasons: list[str] = field(default_factory=list)
    checks: list[CheckResult] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)


def _error_code(execution: TaskExecution) -> str | None:
    response = execution.trajectory.response
    if response is None:
        return None
    if response.ok:
        return None
    err = response.error or {}
    code = err.get("code")
    return str(code) if code is not None else None


def _actuals(execution: TaskExecution) -> dict[str, Any]:
    traj = execution.trajectory
    response = traj.response
    return {
        "ok": None if response is None else response.ok,
        "error_code": _error_code(execution),
        "agent_name": traj.agent_name,
        "agent_cli": traj.agent_cli,
        "agent_role": traj.agent_role,
        "op_in_allowlist": traj.op_in_allowlist,
        "attempts": traj.attempts,
        "retry_count": max(0, traj.attempts - 1) if traj.attempts else 0,
        "circuit_state": traj.circuit_state,
        "output": (
            (response.result or {}).get("output")
            if response is not None and response.ok
            else None
        ),
    }


def score_task(
    execution: TaskExecution,
    *,
    llm_judge: bool = False,
) -> ScoreResult:
    """Score a task execution against its ``expected`` assertions."""
    task = execution.task
    expected = task.expected
    actuals = _actuals(execution)
    checks: list[CheckResult] = []
    reasons: list[str] = []

    if execution.error:
        reasons.append(f"execution error: {execution.error}")
        return ScoreResult(
            task_id=task.id,
            passed=False,
            score=0.0,
            must_pass=task.must_pass,
            reasons=reasons,
            checks=checks,
            tags=list(task.tags),
        )

    # Deterministic field checks — only fields present in expected are scored.
    field_names = (
        "ok",
        "error_code",
        "agent_name",
        "agent_cli",
        "agent_role",
        "op_in_allowlist",
        "attempts",
        "retry_count",
        "circuit_state",
    )
    for name in field_names:
        if name not in expected:
            continue
        exp = expected[name]
        act = actuals.get(name)
        passed = act == exp
        checks.append(
            CheckResult(
                name=name,
                passed=passed,
                expected=exp,
                actual=act,
            )
        )
        if not passed:
            reasons.append(f"{name}: expected {exp!r}, got {act!r}")

    # Optional substring check on successful output
    if "output_contains" in expected:
        needle = str(expected["output_contains"])
        hay = str(actuals.get("output") or "")
        passed = needle in hay
        checks.append(
            CheckResult(
                name="output_contains",
                passed=passed,
                expected=needle,
                actual=hay[:200],
            )
        )
        if not passed:
            reasons.append(f"output_contains: {needle!r} not found in output")

    # Optional allowlist trajectory: chosen agent must only advertise listed ops
    if "allowed_mat_ops_subset_of" in expected:
        allowed = set(execution.trajectory.allowed_mat_ops)
        ceiling = set(expected["allowed_mat_ops_subset_of"])
        passed = allowed.issubset(ceiling)
        checks.append(
            CheckResult(
                name="allowed_mat_ops_subset_of",
                passed=passed,
                expected=sorted(ceiling),
                actual=sorted(allowed),
            )
        )
        if not passed:
            reasons.append(
                f"allowed_mat_ops {sorted(allowed)} not subset of {sorted(ceiling)}"
            )

    if llm_judge and expected.get("judge_rubric"):
        judge = judge_output(
            output=str(actuals.get("output") or ""),
            rubric=str(expected["judge_rubric"]),
        )
        checks.append(
            CheckResult(
                name="llm_judge",
                passed=judge.passed,
                expected=expected["judge_rubric"],
                actual=judge.score,
                detail=judge.reason,
            )
        )
        if not judge.passed:
            reasons.append(f"llm_judge: {judge.reason}")

    if not checks:
        reasons.append("no expected checks defined")
        return ScoreResult(
            task_id=task.id,
            passed=False,
            score=0.0,
            must_pass=task.must_pass,
            reasons=reasons,
            checks=checks,
            tags=list(task.tags),
        )

    passed_count = sum(1 for c in checks if c.passed)
    score = passed_count / len(checks)
    min_score = float(expected.get("min_score", 1.0))
    if min_score >= 1.0:
        passed = all(c.passed for c in checks)
    else:
        passed = score + 1e-9 >= min_score

    if passed and not reasons:
        reasons.append("all checks passed")

    return ScoreResult(
        task_id=task.id,
        passed=passed,
        score=round(score, 4),
        must_pass=task.must_pass,
        reasons=reasons,
        checks=checks,
        tags=list(task.tags),
    )
