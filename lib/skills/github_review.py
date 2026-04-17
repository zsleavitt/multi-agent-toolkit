"""GitHub PR review posting via gh CLI."""

from __future__ import annotations

from collections import Counter
from typing import Any

# Severity levels in order of increasing importance
SEVERITY_ORDER = ["info", "suggestion", "issue", "blocker"]

# Emoji mapping for severities
SEVERITY_EMOJI = {
    "blocker": "\U0001f6ab",  # 🚫
    "issue": "\u26a0\ufe0f",  # ⚠️
    "suggestion": "\U0001f4a1",  # 💡
    "info": "\u2139\ufe0f",  # ℹ️
}


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


def format_summary(findings: list[dict[str, Any]]) -> str:
    """
    Format a brief summary of findings by severity.

    Args:
        findings: List of finding dicts with 'severity' key.

    Returns:
        Markdown summary string.
    """
    counts = Counter(f["severity"] for f in findings)

    parts = []
    for severity in ["blocker", "issue", "suggestion", "info"]:
        count = counts.get(severity, 0)
        if count > 0:
            emoji = SEVERITY_EMOJI[severity]
            # Pluralize: "1 blocker" vs "2 blockers"
            label = severity if count == 1 else f"{severity}s"
            parts.append(f"{emoji} {count} {label}")

    counts_line = " \u00b7 ".join(parts) if parts else "No findings"

    return f"## Review Summary\n\n{counts_line}\n\n*Posted via /review-pr*"
