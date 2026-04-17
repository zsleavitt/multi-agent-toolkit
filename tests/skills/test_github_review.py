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
