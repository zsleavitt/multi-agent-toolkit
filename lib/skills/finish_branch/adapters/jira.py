"""Jira close adapter (stub - reads credentials from environment)."""

from __future__ import annotations

import os
from typing import Any

from lib.skills.finish_branch.adapters.base import CloseResult


class JiraCloseAdapter:
    """
    Close Jira issues via REST API.

    Configuration (from ai-team.repo.json):
        - base_url: Jira instance URL (e.g., "https://company.atlassian.net")
        - project_key: Jira project key (e.g., "PROJ")
        - done_transition: Transition name or ID for "Done" (default: "Done")

    Environment variables:
        - JIRA_EMAIL: User email for authentication
        - JIRA_API_TOKEN: API token for authentication
    """

    adapter_name = "jira"

    def __init__(self, config: dict[str, Any]) -> None:
        self.base_url = config.get("base_url", "")
        self.project_key = config.get("project_key", "")
        self.done_transition = config.get("done_transition", "Done")
        self.email = os.environ.get("JIRA_EMAIL", "")
        self.api_token = os.environ.get("JIRA_API_TOKEN", "")

    def close(self, work_item_ref: str, comment: str | None = None) -> CloseResult:
        """
        Transition a Jira issue to Done.

        Args:
            work_item_ref: Jira issue key (e.g., "PROJ-123").
            comment: Optional comment to add.

        Returns:
            CloseResult with success/failure.
        """
        if not self.email or not self.api_token:
            return CloseResult(
                ok=False,
                message="",
                error="Jira credentials not configured. Set JIRA_EMAIL and JIRA_API_TOKEN environment variables.",
            )

        if not self.base_url:
            return CloseResult(
                ok=False,
                message="",
                error="Jira base_url not configured in ai-team.repo.json.",
            )

        # TODO: Implement actual Jira API call
        return CloseResult(
            ok=False,
            message="",
            error=f"Jira adapter not fully implemented. Would close {work_item_ref} at {self.base_url}.",
        )
