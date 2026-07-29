"""Optional LLM-as-judge path (off by default; CI must not enable it)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class JudgeResult:
    passed: bool
    score: float
    reason: str


def judge_output(*, output: str, rubric: str) -> JudgeResult:
    """Heuristic stand-in for an LLM judge.

    Real LLM judging is intentionally not wired here so CI stays free of
    network/API dependencies. When ``--llm-judge`` is set, this function applies
    a deterministic rubric: non-empty output that mentions key tokens from the
    rubric string (split on whitespace, length > 3).
    """
    if not output.strip():
        return JudgeResult(passed=False, score=0.0, reason="empty output")

    tokens = [t.strip(".,;:").lower() for t in rubric.split() if len(t.strip()) > 3]
    if not tokens:
        return JudgeResult(
            passed=True,
            score=1.0,
            reason="no rubric tokens; accepted non-empty output",
        )

    hay = output.lower()
    hits = sum(1 for t in tokens if t in hay)
    score = hits / len(tokens)
    passed = score >= 0.5
    return JudgeResult(
        passed=passed,
        score=round(score, 4),
        reason=f"matched {hits}/{len(tokens)} rubric tokens",
    )
