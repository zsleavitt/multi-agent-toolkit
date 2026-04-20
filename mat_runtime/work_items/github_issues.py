"""GitHub Issues work item adapter.

This adapter provides the interface and configuration for GitHub Issues management.
Actual MCP tool calls are made by the /ticket skill in the orchestrator context.

The adapter handles:
- Field mapping between MAT fields and GitHub Issue properties
- Building payloads for GitHub MCP tools
- Parsing GitHub responses into WorkItem objects

Usage from /ticket skill:
    adapter = get_adapter_from_profile(repo_root)
    # adapter.build_create_payload(item) -> dict for issue_write
    # adapter.build_list_payload(status, limit) -> dict for list_issues
    # adapter.parse_github_issue(issue) -> WorkItem
"""

from __future__ import annotations

from typing import Any

from mat_runtime.work_items.base import WorkItem, WorkItemAdapter, WorkItemResult
from mat_runtime.work_items.registry import register_adapter


@register_adapter("github_issues")
class GitHubIssuesAdapter(WorkItemAdapter):
    """
    GitHub Issues adapter for work items.

    Configuration (from ai-team.repo.json):
        - owner: GitHub repository owner
        - repo: GitHub repository name
        - priority_labels: Mapping of priority values to GitHub labels
        - status_labels: Mapping of status values to GitHub labels
    """

    adapter_name = "github_issues"

    # MCP tool names for GitHub operations
    MCP_TOOL_CREATE = "Github-Gusto__issue_write"
    MCP_TOOL_UPDATE = "Github-Gusto__issue_write"
    MCP_TOOL_QUERY = "Github-Gusto__list_issues"
    MCP_TOOL_READ = "Github-Gusto__issue_read"

    # Default priority label mapping
    DEFAULT_PRIORITY_LABELS = {
        "P0": "priority:critical",
        "P1": "priority:high",
        "P2": "priority:medium",
    }

    # Default status mapping (GitHub uses OPEN/CLOSED states)
    DEFAULT_STATUS_MAP = {
        "Backlog": "OPEN",
        "Ready": "OPEN",
        "In progress": "OPEN",
        "Done": "CLOSED",
        "Blocked": "OPEN",
    }

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        self.owner = config.get("owner", "")
        self.repo = config.get("repo", "")
        self._priority_labels = {
            **self.DEFAULT_PRIORITY_LABELS,
            **config.get("priority_labels", {}),
        }
        self._status_map = {
            **self.DEFAULT_STATUS_MAP,
            **config.get("status_map", {}),
        }

    def get_field_name(self, mat_field: str) -> str:
        """Map MAT field name to GitHub field name."""
        mapping = {
            "title": "title",
            "description": "body",
            "status": "state",
            "priority": "labels",
            "ticket_id": "number",
        }
        return mapping.get(mat_field, mat_field)

    def _priority_to_label(self, priority: str | None) -> str | None:
        """Convert MAT priority to GitHub label."""
        if not priority:
            return None
        return self._priority_labels.get(priority, priority)

    def _label_to_priority(self, labels: list[str]) -> str | None:
        """Convert GitHub labels to MAT priority."""
        # Reverse lookup
        label_to_priority = {v: k for k, v in self._priority_labels.items()}
        for label in labels:
            if label in label_to_priority:
                return label_to_priority[label]
        return None

    def _status_to_state(self, status: str | None) -> str:
        """Convert MAT status to GitHub state (OPEN/CLOSED)."""
        if not status:
            return "OPEN"
        return self._status_map.get(status, "OPEN")

    def _state_to_status(self, state: str) -> str:
        """Convert GitHub state to MAT status."""
        return "Done" if state == "CLOSED" else "Backlog"

    def build_create_payload(self, item: WorkItem) -> dict[str, Any]:
        """
        Build payload for Github-Gusto__issue_write MCP tool (create).

        Returns dict with fields for creating a GitHub issue.
        """
        payload: dict[str, Any] = {
            "method": "create",
            "owner": self.owner,
            "repo": self.repo,
            "title": item.title,
        }

        if item.description:
            # Build a structured body with priority and description
            body_parts = []
            if item.priority:
                body_parts.append(f"**Priority:** {item.priority}")
            if item.status:
                body_parts.append(f"**Status:** {item.status}")
            if body_parts:
                body_parts.append("")  # Empty line
            body_parts.append(item.description)
            payload["body"] = "\n".join(body_parts)
        elif item.priority or item.status:
            body_parts = []
            if item.priority:
                body_parts.append(f"**Priority:** {item.priority}")
            if item.status:
                body_parts.append(f"**Status:** {item.status}")
            payload["body"] = "\n".join(body_parts)

        # Add priority as a label
        labels = []
        if item.priority:
            label = self._priority_to_label(item.priority)
            if label:
                labels.append(label)
        if labels:
            payload["labels"] = labels

        return payload

    def build_update_payload(self, item: WorkItem) -> dict[str, Any]:
        """
        Build payload for Github-Gusto__issue_write MCP tool (update).

        Returns dict with fields for updating a GitHub issue.
        """
        payload: dict[str, Any] = {
            "method": "update",
            "owner": self.owner,
            "repo": self.repo,
            "issue_number": int(item.id) if item.id else None,
        }

        if item.title:
            payload["title"] = item.title

        if item.status:
            state = self._status_to_state(item.status)
            payload["state"] = state.lower()  # GitHub API uses lowercase
            if state == "CLOSED":
                payload["state_reason"] = "completed"

        if item.priority:
            label = self._priority_to_label(item.priority)
            if label:
                payload["labels"] = [label]

        return payload

    def build_query(
        self,
        status: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        """
        Build payload for Github-Gusto__list_issues MCP tool.

        Returns dict with query parameters for listing GitHub issues.
        """
        payload: dict[str, Any] = {
            "owner": self.owner,
            "repo": self.repo,
            "perPage": min(limit, 100),  # GitHub max is 100
        }

        # Map status to GitHub state
        if status:
            state = self._status_to_state(status)
            payload["state"] = state

        return payload

    def parse_github_issue(self, issue: dict[str, Any]) -> WorkItem:
        """Parse a GitHub issue response into a WorkItem."""
        labels = [
            label.get("name", label) if isinstance(label, dict) else label
            for label in issue.get("labels", [])
        ]

        return WorkItem(
            id=str(issue.get("number", "")),
            ticket_id=issue.get("number"),
            title=issue.get("title", ""),
            status=self._state_to_status(issue.get("state", "OPEN")),
            priority=self._label_to_priority(labels),
            url=issue.get("url") or issue.get("html_url"),
            description=issue.get("body", ""),
            metadata={
                "labels": labels,
                "user": issue.get("user", {}).get("login"),
                "created_at": issue.get("created_at"),
                "updated_at": issue.get("updated_at"),
            },
        )

    def parse_github_results(self, results: list[dict[str, Any]]) -> list[WorkItem]:
        """Parse multiple GitHub issue responses into WorkItems."""
        return [self.parse_github_issue(issue) for issue in results]

    # Abstract method implementations
    # These return "not implemented" since actual calls go through MCP

    def create(self, item: WorkItem) -> WorkItemResult:
        """
        Create requires MCP context. Use build_create_payload() instead.

        The /ticket skill should:
        1. Call adapter.build_create_payload(item)
        2. Call Github-Gusto__issue_write MCP tool with the payload
        3. Parse the response with parse_github_issue()
        """
        return WorkItemResult(
            ok=False,
            error="Direct create not supported. Use build_create_payload() with MCP tools.",
        )

    def update(self, item: WorkItem) -> WorkItemResult:
        """
        Update requires MCP context. Use build_update_payload() instead.
        """
        return WorkItemResult(
            ok=False,
            error="Direct update not supported. Use build_update_payload() with MCP tools.",
        )

    def get(self, item_id: str) -> WorkItemResult:
        """
        Get requires MCP context. Use Github-Gusto__issue_read MCP tool.
        """
        return WorkItemResult(
            ok=False,
            error="Direct get not supported. Use issue_read MCP tool.",
        )

    def list(
        self,
        status: str | None = None,
        limit: int = 50,
    ) -> WorkItemResult:
        """
        List requires MCP context. Use build_query() instead.
        """
        return WorkItemResult(
            ok=False,
            error="Direct list not supported. Use build_query() with MCP tools.",
        )
