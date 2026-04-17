# /review-pr GitHub PR Comments Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend `/review-pr` to post review findings as inline comments on GitHub PRs via `gh api`.

**Architecture:** New `github_review.py` module handles all GitHub interaction. Existing `review_pr.py` gains `--post` and `--min-severity` flags that trigger GitHub posting after the reviewer agent completes.

**Tech Stack:** Python 3, `gh` CLI, subprocess, tempfile, JSON

---

## File Structure

| File | Responsibility |
|------|----------------|
| `lib/skills/github_review.py` (NEW) | GitHub interaction: PR detection, payload building, posting |
| `lib/skills/review-pr/review_pr.py` (MODIFY) | Add CLI flags, integrate GitHub posting |
| `tests/skills/__init__.py` (NEW) | Skills test package init |
| `tests/skills/test_github_review.py` (NEW) | Unit tests for github_review module |

Note: `github_review.py` is placed in `lib/skills/` (not `lib/skills/review-pr/`) because Python cannot import from directories with hyphens. This also enables reuse by other skills.

---

### Task 1: Create test directory structure

**Files:**
- Create: `tests/skills/__init__.py`

- [ ] **Step 1: Create test package directory**

```bash
mkdir -p tests/skills
```

- [ ] **Step 2: Create init file**

Create `tests/skills/__init__.py`:
```python
"""Skills test package."""
```

- [ ] **Step 3: Verify structure**

Run: `ls -la tests/skills/`
Expected: `__init__.py` file present

- [ ] **Step 4: Commit**

```bash
git add tests/skills/
git commit -m "test: add skills test package structure"
```

---

### Task 2: Implement severity filtering and summary formatting

**Files:**
- Create: `lib/skills/github_review.py`
- Create: `tests/skills/test_github_review.py`

- [ ] **Step 1: Write failing test for severity filtering**

Create `tests/skills/test_github_review.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/skills/test_github_review.py -v`
Expected: FAIL with "cannot import name 'filter_findings_by_severity'"

- [ ] **Step 3: Write minimal implementation**

Create `lib/skills/github_review.py`:
```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/skills/test_github_review.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add lib/skills/github_review.py tests/skills/test_github_review.py
git commit -m "feat(review-pr): add severity filtering for GitHub posting"
```

---

### Task 3: Implement summary formatting

**Files:**
- Modify: `lib/skills/github_review.py`
- Modify: `tests/skills/test_github_review.py`

- [ ] **Step 1: Write failing test for summary formatting**

Add to `tests/skills/test_github_review.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/skills/test_github_review.py::test_format_summary_counts_by_severity -v`
Expected: FAIL with "cannot import name 'format_summary'"

- [ ] **Step 3: Write implementation**

Add to `lib/skills/github_review.py`:
```python
from collections import Counter

# Emoji mapping for severities
SEVERITY_EMOJI = {
    "blocker": "\U0001f6ab",  # 🚫
    "issue": "\u26a0\ufe0f",  # ⚠️
    "suggestion": "\U0001f4a1",  # 💡
    "info": "\u2139\ufe0f",  # ℹ️
}


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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/skills/test_github_review.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add lib/skills/github_review.py tests/skills/test_github_review.py
git commit -m "feat(review-pr): add summary formatting with severity counts"
```

---

### Task 4: Implement inline comment formatting

**Files:**
- Modify: `lib/skills/github_review.py`
- Modify: `tests/skills/test_github_review.py`

- [ ] **Step 1: Write failing test for inline comment formatting**

Add to `tests/skills/test_github_review.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/skills/test_github_review.py::test_format_inline_comment_includes_severity_and_category -v`
Expected: FAIL with "cannot import name 'format_inline_comment'"

- [ ] **Step 3: Write implementation**

Add to `lib/skills/github_review.py`:
```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/skills/test_github_review.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add lib/skills/github_review.py tests/skills/test_github_review.py
git commit -m "feat(review-pr): add inline comment formatting"
```

---

### Task 5: Implement review event determination

**Files:**
- Modify: `lib/skills/github_review.py`
- Modify: `tests/skills/test_github_review.py`

- [ ] **Step 1: Write failing tests for event determination**

Add to `tests/skills/test_github_review.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/skills/test_github_review.py::test_determine_review_event_request_changes_when_blocker -v`
Expected: FAIL with "cannot import name 'determine_review_event'"

- [ ] **Step 3: Write implementation**

Add to `lib/skills/github_review.py`:
```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/skills/test_github_review.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add lib/skills/github_review.py tests/skills/test_github_review.py
git commit -m "feat(review-pr): add review event determination logic"
```

---

### Task 6: Implement payload building

**Files:**
- Modify: `lib/skills/github_review.py`
- Modify: `tests/skills/test_github_review.py`

- [ ] **Step 1: Write failing tests for payload building**

Add to `tests/skills/test_github_review.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/skills/test_github_review.py::test_build_review_payload_creates_correct_structure -v`
Expected: FAIL with "cannot import name 'build_review_payload'"

- [ ] **Step 3: Write implementation**

Add to `lib/skills/github_review.py`:
```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/skills/test_github_review.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add lib/skills/github_review.py tests/skills/test_github_review.py
git commit -m "feat(review-pr): add review payload building"
```

---

### Task 7: Implement PR detection via gh CLI

**Files:**
- Modify: `lib/skills/github_review.py`
- Modify: `tests/skills/test_github_review.py`

- [ ] **Step 1: Write failing tests for PR detection**

Add to `tests/skills/test_github_review.py`:
```python
from unittest.mock import patch, MagicMock
import subprocess


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/skills/test_github_review.py::test_detect_pr_for_branch_returns_pr_info_when_found -v`
Expected: FAIL with "cannot import name 'detect_pr_for_branch'"

- [ ] **Step 3: Write implementation**

Add to `lib/skills/github_review.py`:
```python
import json
import subprocess


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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/skills/test_github_review.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add lib/skills/github_review.py tests/skills/test_github_review.py
git commit -m "feat(review-pr): add PR detection via gh CLI"
```

---

### Task 8: Implement gh CLI checks

**Files:**
- Modify: `lib/skills/github_review.py`
- Modify: `tests/skills/test_github_review.py`

- [ ] **Step 1: Write failing tests for gh CLI checks**

Add to `tests/skills/test_github_review.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/skills/test_github_review.py::test_check_gh_cli_returns_true_when_installed_and_authed -v`
Expected: FAIL with "cannot import name 'check_gh_cli'"

- [ ] **Step 3: Write implementation**

Add to `lib/skills/github_review.py`:
```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/skills/test_github_review.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add lib/skills/github_review.py tests/skills/test_github_review.py
git commit -m "feat(review-pr): add gh CLI availability check"
```

---

### Task 9: Implement review posting

**Files:**
- Modify: `lib/skills/github_review.py`
- Modify: `tests/skills/test_github_review.py`

- [ ] **Step 1: Write failing tests for review posting**

Add to `tests/skills/test_github_review.py`:
```python
import tempfile
import os


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/skills/test_github_review.py::test_post_review_calls_gh_api_with_payload -v`
Expected: FAIL with "cannot import name 'post_review'"

- [ ] **Step 3: Write implementation**

Add to `lib/skills/github_review.py`:
```python
import tempfile


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
```

- [ ] **Step 4: Add os import at top of file**

Ensure `import os` is at the top of `lib/skills/github_review.py` (add after `import json` if not present).

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/skills/test_github_review.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add lib/skills/github_review.py tests/skills/test_github_review.py
git commit -m "feat(review-pr): add review posting via gh api"
```

---

### Task 10: Update review_pr.py with new CLI flags

**Files:**
- Modify: `lib/skills/review-pr/review_pr.py`

- [ ] **Step 1: Add new argument flags**

In `lib/skills/review-pr/review_pr.py`, add after the existing `parser.add_argument` calls (around line 32):

```python
    parser.add_argument("--post", "-p", action="store_true", help="Post findings as GitHub PR review")
    parser.add_argument(
        "--min-severity",
        "-m",
        choices=["info", "suggestion", "issue", "blocker"],
        default="info",
        help="Minimum severity to post (default: info)",
    )
```

- [ ] **Step 2: Verify CLI help shows new flags**

Run: `python lib/skills/review-pr/review_pr.py --help`
Expected: Output includes `--post` and `--min-severity` flags

- [ ] **Step 3: Commit**

```bash
git add lib/skills/review-pr/review_pr.py
git commit -m "feat(review-pr): add --post and --min-severity CLI flags"
```

---

### Task 11: Integrate GitHub posting into review_pr.py

**Files:**
- Modify: `lib/skills/review-pr/review_pr.py`

- [ ] **Step 1: Add imports for github_review module**

At the top of `lib/skills/review-pr/review_pr.py`, after the existing imports, add:

```python
from lib.skills.github_review import (
    check_gh_cli,
    detect_pr_for_branch,
    filter_findings_by_severity,
    build_review_payload,
    post_review,
)
```

- [ ] **Step 2: Add GitHub posting logic after reviewer invocation**

In the `main()` function, after `response = router.invoke("reviewer", request)` and before the JSON/success output block, add:

```python
    # Handle --post flag for GitHub PR comments
    posted_pr = None
    if args.post and response.ok:
        # Check gh CLI availability
        gh_ok, gh_error = check_gh_cli()
        if not gh_ok:
            print(f"Error: {gh_error}", file=sys.stderr)
            print("\nFalling back to CLI output only.\n", file=sys.stderr)
        else:
            # Detect PR for current branch
            pr_info = detect_pr_for_branch()
            if pr_info is None:
                # Prompt to create PR
                create = input("No PR found for current branch. Create one? [y/N] ").strip().lower()
                if create == "y":
                    result = subprocess.run(["gh", "pr", "create"], check=False)
                    if result.returncode == 0:
                        pr_info = detect_pr_for_branch()

            if pr_info:
                # Get findings from response
                findings = response.result.get("findings", [])
                filtered = filter_findings_by_severity(findings, args.min_severity)

                if filtered:
                    payload = build_review_payload(filtered)
                    post_ok, post_error = post_review(pr_info, payload)
                    if post_ok:
                        posted_pr = pr_info["number"]
                    else:
                        print(f"Error posting review: {post_error}", file=sys.stderr)
                        print("\nFalling back to CLI output only.\n", file=sys.stderr)
                else:
                    print("No findings meet minimum severity threshold.", file=sys.stderr)
            else:
                print("\nNo PR available. Showing CLI output only.\n", file=sys.stderr)
```

- [ ] **Step 3: Add subprocess import**

Add at top of file if not present:
```python
import subprocess
```

- [ ] **Step 4: Add posted message after output**

After the output block (after `print(format_success(response, "Code Review"))`), add:

```python
    if posted_pr:
        print(f"\n✓ Posted review to PR #{posted_pr}")
```

- [ ] **Step 5: Verify the script runs**

Run: `python lib/skills/review-pr/review_pr.py --help`
Expected: No import errors, help displays

- [ ] **Step 6: Commit**

```bash
git add lib/skills/review-pr/review_pr.py
git commit -m "feat(review-pr): integrate GitHub posting with --post flag"
```

---

### Task 12: Update instructions.md documentation

**Files:**
- Modify: `lib/skills/review-pr/instructions.md`

- [ ] **Step 1: Update usage section**

Replace the Usage section in `lib/skills/review-pr/instructions.md`:

```markdown
## Usage

```
/review-pr <target> [--post] [--min-severity info|suggestion|issue|blocker]
```

### Options

| Flag | Description |
|------|-------------|
| `--post`, `-p` | Post findings as GitHub PR review |
| `--min-severity`, `-m` | Minimum severity to post (default: `info`) |
```

- [ ] **Step 2: Add GitHub posting examples**

Add after the existing examples section:

```markdown
### Post review to GitHub PR
```
/review-pr Review staged changes --post
```

### Post only issues and blockers
```
/review-pr Review src/api/ --post --min-severity issue
```
```

- [ ] **Step 3: Add GitHub requirements note**

Add a new section before "What the reviewer checks":

```markdown
## GitHub Integration

When using `--post`, the skill will:
1. Check that `gh` CLI is installed and authenticated
2. Detect if there's an open PR for the current branch
3. Post inline comments for each finding
4. Submit a review with appropriate status (REQUEST_CHANGES if blockers/issues, COMMENT otherwise)

**Requirements:**
- GitHub CLI (`gh`) installed and authenticated (`gh auth login`)
- Current branch must have an open PR (or you'll be prompted to create one)
```

- [ ] **Step 4: Commit**

```bash
git add lib/skills/review-pr/instructions.md
git commit -m "docs(review-pr): document GitHub posting feature"
```

---

### Task 13: Final integration test

**Files:**
- None (manual verification)

- [ ] **Step 1: Run full test suite**

Run: `pytest tests/ -v`
Expected: All tests pass

- [ ] **Step 2: Test CLI without --post (existing behavior)**

Run: `python lib/skills/review-pr/review_pr.py "Review this file" --repo-root . --json`
Expected: Returns JSON response (may fail on actual review, but CLI should work)

- [ ] **Step 3: Test --post flag requires gh**

Run with gh not in PATH (if possible) or check error handling:
```bash
python lib/skills/review-pr/review_pr.py "test" --post --repo-root .
```
Expected: Either posts successfully or shows appropriate error message

- [ ] **Step 4: Create final commit**

```bash
git add -A
git commit -m "feat(review-pr): complete GitHub PR comment posting feature

- Add --post flag to enable GitHub PR review posting
- Add --min-severity flag for filtering (default: info)
- Auto-detect PR for current branch, prompt to create if missing
- Post inline comments per finding with severity/category
- Post brief summary with severity counts
- Auto-determine review event (REQUEST_CHANGES vs COMMENT)
- Fall back to CLI output on any GitHub error"
```

---

## Summary

| Task | Description | Files |
|------|-------------|-------|
| 1 | Test directory structure | tests/skills/__init__.py |
| 2 | Severity filtering | lib/skills/github_review.py, tests/skills/test_github_review.py |
| 3 | Summary formatting | lib/skills/github_review.py, tests/skills/test_github_review.py |
| 4 | Inline comment formatting | lib/skills/github_review.py, tests/skills/test_github_review.py |
| 5 | Review event determination | lib/skills/github_review.py, tests/skills/test_github_review.py |
| 6 | Payload building | lib/skills/github_review.py, tests/skills/test_github_review.py |
| 7 | PR detection | lib/skills/github_review.py, tests/skills/test_github_review.py |
| 8 | gh CLI checks | lib/skills/github_review.py, tests/skills/test_github_review.py |
| 9 | Review posting | lib/skills/github_review.py, tests/skills/test_github_review.py |
| 10 | CLI flags | lib/skills/review-pr/review_pr.py |
| 11 | Integration | lib/skills/review-pr/review_pr.py |
| 12 | Documentation | lib/skills/review-pr/instructions.md |
| 13 | Final verification | (manual) |
