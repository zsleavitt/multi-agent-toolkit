"""Tests for github_review module."""

from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock
import subprocess
import tempfile
import os


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


def test_format_inline_comment_includes_severity_and_category():
    """Inline comment should format as **[severity]** category: message."""
    from lib.skills.github_review import format_inline_comment

    finding = {
        "severity": "blocker",
        "category": "security",
        "message": "SQL injection risk",
        "path": "db.py",
        "line": 42,
    }

    result = format_inline_comment(finding)

    assert result == "**[blocker]** security: SQL injection risk"


def test_format_inline_comment_handles_missing_category():
    """When category is missing, omit it from the comment."""
    from lib.skills.github_review import format_inline_comment

    finding = {
        "severity": "suggestion",
        "message": "Consider renaming this variable",
        "path": "utils.py",
        "line": 10,
    }

    result = format_inline_comment(finding)

    assert result == "**[suggestion]** Consider renaming this variable"


def test_determine_review_event_request_changes_when_blocker():
    """REQUEST_CHANGES when any blocker is present."""
    from lib.skills.github_review import determine_review_event

    findings = [
        {"severity": "blocker", "path": "a.py", "message": "msg"},
        {"severity": "info", "path": "b.py", "message": "msg"},
    ]

    assert determine_review_event(findings) == "REQUEST_CHANGES"


def test_determine_review_event_request_changes_when_issue():
    """REQUEST_CHANGES when any issue is present (no blockers)."""
    from lib.skills.github_review import determine_review_event

    findings = [
        {"severity": "issue", "path": "a.py", "message": "msg"},
        {"severity": "suggestion", "path": "b.py", "message": "msg"},
    ]

    assert determine_review_event(findings) == "REQUEST_CHANGES"


def test_determine_review_event_comment_when_only_suggestions():
    """COMMENT when only suggestions and info."""
    from lib.skills.github_review import determine_review_event

    findings = [
        {"severity": "suggestion", "path": "a.py", "message": "msg"},
        {"severity": "info", "path": "b.py", "message": "msg"},
    ]

    assert determine_review_event(findings) == "COMMENT"


def test_determine_review_event_comment_when_empty():
    """COMMENT when no findings."""
    from lib.skills.github_review import determine_review_event

    assert determine_review_event([]) == "COMMENT"


def test_build_review_payload_creates_correct_structure():
    """Payload should have event, body, and comments array."""
    from lib.skills.github_review import build_review_payload

    findings = [
        {"severity": "issue", "path": "src/a.py", "line": 10, "message": "Bug here", "category": "correctness"},
    ]

    payload = build_review_payload(findings)

    assert payload["event"] == "REQUEST_CHANGES"
    assert "Review Summary" in payload["body"]
    assert len(payload["comments"]) == 1
    assert payload["comments"][0]["path"] == "src/a.py"
    assert payload["comments"][0]["line"] == 10
    assert "**[issue]**" in payload["comments"][0]["body"]


def test_build_review_payload_omits_line_when_missing():
    """Comments without line numbers should omit the line field."""
    from lib.skills.github_review import build_review_payload

    findings = [
        {"severity": "suggestion", "path": "src/b.py", "message": "General suggestion"},
    ]

    payload = build_review_payload(findings)

    assert "line" not in payload["comments"][0]


def test_build_review_payload_handles_empty_findings():
    """Empty findings should produce payload with no comments."""
    from lib.skills.github_review import build_review_payload

    payload = build_review_payload([])

    assert payload["event"] == "COMMENT"
    assert payload["comments"] == []


def test_detect_pr_for_branch_returns_pr_info_when_found():
    """Should return PR number and repo when PR exists."""
    from lib.skills.github_review import detect_pr_for_branch

    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = '{"number": 42, "headRepository": {"owner": {"login": "myorg"}, "name": "myrepo"}}'

    with patch("subprocess.run", return_value=mock_result) as mock_run:
        result = detect_pr_for_branch()

        mock_run.assert_called_once()
        assert result == {"number": 42, "owner": "myorg", "repo": "myrepo"}


def test_detect_pr_for_branch_returns_none_when_no_pr():
    """Should return None when no PR exists for current branch."""
    from lib.skills.github_review import detect_pr_for_branch

    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stderr = "no pull requests found"

    with patch("subprocess.run", return_value=mock_result):
        result = detect_pr_for_branch()

        assert result is None


def test_check_gh_cli_returns_true_when_installed_and_authed():
    """Should return True when gh is installed and authenticated."""
    from lib.skills.github_review import check_gh_cli

    mock_result = MagicMock()
    mock_result.returncode = 0

    with patch("subprocess.run", return_value=mock_result):
        ok, error = check_gh_cli()

        assert ok is True
        assert error is None


def test_check_gh_cli_returns_error_when_not_installed():
    """Should return error message when gh is not installed."""
    from lib.skills.github_review import check_gh_cli

    with patch("subprocess.run", side_effect=FileNotFoundError()):
        ok, error = check_gh_cli()

        assert ok is False
        assert "not found" in error.lower()


def test_check_gh_cli_returns_error_when_not_authed():
    """Should return error message when gh is not authenticated."""
    from lib.skills.github_review import check_gh_cli

    mock_result = MagicMock()
    mock_result.returncode = 1

    with patch("subprocess.run", return_value=mock_result):
        ok, error = check_gh_cli()

        assert ok is False
        assert "not authenticated" in error.lower()


def test_post_review_calls_gh_api_with_payload():
    """Should call gh api with correct endpoint and payload."""
    from lib.skills.github_review import post_review

    pr_info = {"number": 42, "owner": "myorg", "repo": "myrepo"}
    payload = {"event": "COMMENT", "body": "summary", "comments": []}

    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = '{"id": 12345}'

    with patch("subprocess.run", return_value=mock_result) as mock_run:
        ok, error = post_review(pr_info, payload)

        assert ok is True
        assert error is None
        # Verify gh api was called
        call_args = mock_run.call_args[0][0]
        assert "gh" in call_args
        assert "api" in call_args
        assert "repos/myorg/myrepo/pulls/42/reviews" in call_args


def test_post_review_returns_error_on_failure():
    """Should return error message when gh api fails."""
    from lib.skills.github_review import post_review

    pr_info = {"number": 42, "owner": "myorg", "repo": "myrepo"}
    payload = {"event": "COMMENT", "body": "summary", "comments": []}

    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stderr = "API error: 422 Unprocessable Entity"

    with patch("subprocess.run", return_value=mock_result):
        ok, error = post_review(pr_info, payload)

        assert ok is False
        assert "422" in error
