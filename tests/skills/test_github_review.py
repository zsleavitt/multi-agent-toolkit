"""Tests for github_review module."""

from __future__ import annotations

import pytest


def test_filter_findings_by_severity_filters_below_threshold():
    """Findings below min_severity should be excluded."""
    from lib.skills.github_review import filter_findings_by_severity

    findings = [
        {"severity": "info", "path": "a.py", "message": "info msg"},
        {"severity": "suggestion", "path": "b.py", "message": "suggestion msg"},
        {"severity": "issue", "path": "c.py", "message": "issue msg"},
        {"severity": "blocker", "path": "d.py", "message": "blocker msg"},
    ]

    result = filter_findings_by_severity(findings, min_severity="issue")

    assert len(result) == 2
    assert result[0]["severity"] == "issue"
    assert result[1]["severity"] == "blocker"


def test_filter_findings_by_severity_includes_all_when_info():
    """When min_severity is info, all findings should be included."""
    from lib.skills.github_review import filter_findings_by_severity

    findings = [
        {"severity": "info", "path": "a.py", "message": "info msg"},
        {"severity": "blocker", "path": "b.py", "message": "blocker msg"},
    ]

    result = filter_findings_by_severity(findings, min_severity="info")

    assert len(result) == 2


def test_format_summary_counts_by_severity():
    """Summary should show emoji + count for each severity present."""
    from lib.skills.github_review import format_summary

    findings = [
        {"severity": "blocker", "path": "a.py", "message": "msg"},
        {"severity": "blocker", "path": "b.py", "message": "msg"},
        {"severity": "issue", "path": "c.py", "message": "msg"},
        {"severity": "suggestion", "path": "d.py", "message": "msg"},
        {"severity": "suggestion", "path": "e.py", "message": "msg"},
        {"severity": "suggestion", "path": "f.py", "message": "msg"},
        {"severity": "info", "path": "g.py", "message": "msg"},
    ]

    result = format_summary(findings)

    assert "2 blockers" in result
    assert "1 issue" in result
    assert "3 suggestions" in result
    assert "1 info" in result
    assert "*Posted via /review-pr*" in result


def test_format_summary_omits_zero_counts():
    """Severities with zero findings should not appear in summary."""
    from lib.skills.github_review import format_summary

    findings = [
        {"severity": "suggestion", "path": "a.py", "message": "msg"},
    ]

    result = format_summary(findings)

    assert "blocker" not in result
    assert "issue" not in result
    assert "1 suggestion" in result
    assert "info" not in result
