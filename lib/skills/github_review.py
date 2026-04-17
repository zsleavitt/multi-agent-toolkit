"""GitHub PR review posting via gh CLI."""

from __future__ import annotations

import json
import subprocess
import tempfile
import os
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


def format_inline_comment(finding: dict[str, Any]) -> str:
    """
    Format a finding as an inline comment body.

    Args:
        finding: Finding dict with severity, message, and optional category.

    Returns:
        Formatted comment body string.
    """
    severity = finding["severity"]
    message = finding["message"]
    category = finding.get("category")

    if category:
        return f"**[{severity}]** {category}: {message}"
    else:
        return f"**[{severity}]** {message}"


def determine_review_event(findings: list[dict[str, Any]]) -> str:
    """
    Determine the GitHub review event type based on findings.

    Args:
        findings: List of finding dicts with 'severity' key.

    Returns:
        "REQUEST_CHANGES" if any blocker or issue, otherwise "COMMENT".
    """
    severities = {f["severity"] for f in findings}
    if "blocker" in severities or "issue" in severities:
        return "REQUEST_CHANGES"
    return "COMMENT"


def build_review_payload(findings: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Build the GitHub API payload for creating a review.

    Args:
        findings: List of finding dicts.

    Returns:
        Dict suitable for POST to /repos/{owner}/{repo}/pulls/{pr}/reviews.
    """
    comments = []
    for finding in findings:
        comment: dict[str, Any] = {
            "path": finding["path"],
            "body": format_inline_comment(finding),
        }
        if "line" in finding:
            comment["line"] = finding["line"]
        comments.append(comment)

    return {
        "event": determine_review_event(findings),
        "body": format_summary(findings),
        "comments": comments,
    }


def check_gh_cli() -> tuple[bool, str | None]:
    """
    Check if gh CLI is installed and authenticated.

    Returns:
        Tuple of (ok, error_message). ok is True if ready, False with message otherwise.
    """
    try:
        result = subprocess.run(
            ["gh", "auth", "status"],
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return False, "GitHub CLI (gh) not found. Install from https://cli.github.com"

    if result.returncode != 0:
        return False, "GitHub CLI not authenticated. Run `gh auth login`"

    return True, None


def detect_pr_for_branch() -> dict[str, Any] | None:
    """
    Detect if there's an open PR for the current branch.

    Returns:
        Dict with 'number', 'owner', 'repo' if PR exists, None otherwise.
    """
    result = subprocess.run(
        ["gh", "pr", "view", "--json", "number,headRepository"],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        return None

    data = json.loads(result.stdout)
    return {
        "number": data["number"],
        "owner": data["headRepository"]["owner"]["login"],
        "repo": data["headRepository"]["name"],
    }


def post_review(
    pr_info: dict[str, Any],
    payload: dict[str, Any],
) -> tuple[bool, str | None]:
    """
    Post a review to a GitHub PR via gh api.

    Args:
        pr_info: Dict with 'number', 'owner', 'repo'.
        payload: Review payload dict.

    Returns:
        Tuple of (ok, error_message). ok is True on success.
    """
    endpoint = f"repos/{pr_info['owner']}/{pr_info['repo']}/pulls/{pr_info['number']}/reviews"

    # Write payload to temp file for --input
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(payload, f)
        temp_path = f.name

    try:
        result = subprocess.run(
            ["gh", "api", endpoint, "--method", "POST", "--input", temp_path],
            capture_output=True,
            text=True,
        )
    finally:
        os.unlink(temp_path)

    if result.returncode != 0:
        return False, result.stderr.strip()

    return True, None
