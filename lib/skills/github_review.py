"""GitHub PR review posting via gh CLI."""

from __future__ import annotations

from typing import Any

# Severity levels in order of increasing importance
SEVERITY_ORDER = ["info", "suggestion", "issue", "blocker"]


def filter_findings_by_severity(
    findings: list[dict[str, Any]],
    min_severity: str = "info",
) -> list[dict[str, Any]]:
    """
    Filter findings to only include those at or above min_severity.

    Args:
        findings: List of finding dicts with 'severity' key.
        min_severity: Minimum severity to include.

    Returns:
        Filtered list of findings.
    """
    min_index = SEVERITY_ORDER.index(min_severity)
    return [
        f for f in findings
        if SEVERITY_ORDER.index(f["severity"]) >= min_index
    ]
