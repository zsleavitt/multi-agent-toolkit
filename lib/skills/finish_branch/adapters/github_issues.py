"""GitHub Issues close adapter using gh CLI."""

from __future__ import annotations

import json
import subprocess
from subprocess import TimeoutExpired
from typing import Any

from lib.skills.finish_branch.adapters.base import CloseResult

GH_TIMEOUT_SECONDS = 30


class GitHubIssuesCloseAdapter:
    """
    Close GitHub Issues using the gh CLI.

    Configuration (from ai-team.repo.json):
        - owner: GitHub repository owner
        - repo: GitHub repository name
    """

    adapter_name = "github_issues"

    def __init__(self, config: dict[str, Any]) -> None:
        self.owner = config.get("owner", "")
        self.repo = config.get("repo", "")

    def _run_gh(self, args: list[str]) -> subprocess.CompletedProcess:
        """Run a gh CLI command."""
        cmd = ["gh"] + args
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
            timeout=GH_TIMEOUT_SECONDS,
        )

    def _find_issue_number(self, work_item_ref: str) -> tuple[int | None, str | None, str | None]:
        """
        Find GitHub issue number by searching for work item reference.

        Returns:
            Tuple of (issue_number, title, url) or (None, None, None) if not found.
        """
        try:
            result = self._run_gh([
                "issue", "list",
                "--repo", f"{self.owner}/{self.repo}",
                "--search", work_item_ref,
                "--json", "number,title,url",
                "--limit", "5",
            ])

            if result.returncode != 0:
                return None, None, None

            issues = json.loads(result.stdout)
            if not issues:
                return None, None, None

            # Find the issue whose title contains the work item ref
            for issue in issues:
                if work_item_ref.upper() in issue.get("title", "").upper():
                    return issue["number"], issue["title"], issue.get("url")

            # If no exact match, return first result
            first = issues[0]
            return first["number"], first["title"], first.get("url")

        except (json.JSONDecodeError, KeyError):
            return None, None, None

    def close(self, work_item_ref: str, comment: str | None = None) -> CloseResult:
        """
        Close a GitHub issue by work item reference.

        Args:
            work_item_ref: Work item reference (e.g., "MAT-42").
            comment: Optional comment to add when closing.

        Returns:
            CloseResult with success/failure details.
        """
        try:
            # Find the issue number
            issue_number, title, url = self._find_issue_number(work_item_ref)

            if issue_number is None:
                return CloseResult(
                    ok=False,
                    message="",
                    error=f"Issue not found for {work_item_ref} in {self.owner}/{self.repo}",
                )

            # Build close command
            close_args = [
                "issue", "close",
                str(issue_number),
                "--repo", f"{self.owner}/{self.repo}",
            ]

            if comment:
                close_args.extend(["--comment", comment])

            result = self._run_gh(close_args)

            if result.returncode != 0:
                return CloseResult(
                    ok=False,
                    message="",
                    item_id=str(issue_number),
                    error=f"Failed to close issue: {result.stderr}",
                )

            return CloseResult(
                ok=True,
                message=f"Closed {work_item_ref} (#{issue_number}: {title})",
                item_id=str(issue_number),
                item_url=url,
            )

        except FileNotFoundError:
            return CloseResult(
                ok=False,
                message="",
                error="gh CLI not found. Install from https://cli.github.com/",
            )
        except TimeoutExpired:
            return CloseResult(
                ok=False,
                message="",
                error=f"gh CLI timed out after {GH_TIMEOUT_SECONDS} seconds",
            )
        except Exception as e:
            return CloseResult(
                ok=False,
                message="",
                error=f"Unexpected error: {e}",
            )
