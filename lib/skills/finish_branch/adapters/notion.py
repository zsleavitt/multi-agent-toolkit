"""Notion close adapter (stub - reads credentials from environment)."""

from __future__ import annotations

import os
from typing import Any

from lib.skills.finish_branch.adapters.base import CloseResult


class NotionCloseAdapter:
    """
    Update Notion page status to Done.

    Configuration (from ai-team.repo.json):
        - database_id: Notion database ID
        - status_property: Property name for status (default: "Status")
        - done_value: Value for done status (default: "Done")

    Environment variables:
        - NOTION_API_KEY: Notion integration API key
    """

    adapter_name = "notion"

    def __init__(self, config: dict[str, Any]) -> None:
        self.database_id = config.get("database_id", "")
        self.status_property = config.get("status_property", "Status")
        self.done_value = config.get("done_value", "Done")
        self.api_key = os.environ.get("NOTION_API_KEY", "")

    def close(self, work_item_ref: str, comment: str | None = None) -> CloseResult:
        """
        Update Notion page status to Done.

        Args:
            work_item_ref: Work item reference to search for.
            comment: Optional comment (not supported by Notion).

        Returns:
            CloseResult with success/failure.
        """
        if not self.api_key:
            return CloseResult(
                ok=False,
                message="",
                error="Notion API key not configured. Set NOTION_API_KEY environment variable.",
            )

        if not self.database_id:
            return CloseResult(
                ok=False,
                message="",
                error="Notion database_id not configured in ai-team.repo.json.",
            )

        # TODO: Implement actual Notion API call
        return CloseResult(
            ok=False,
            message="",
            error=f"Notion adapter not fully implemented. Would update {work_item_ref} status to {self.done_value}.",
        )
