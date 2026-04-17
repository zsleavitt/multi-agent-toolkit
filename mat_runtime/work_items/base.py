"""Base work item adapter for ticket systems."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class WorkItem:
    """Represents a ticket/work item across all adapters."""

    id: str | None = None
    ticket_id: int | str | None = None
    title: str = ""
    description: str = ""
    status: str | None = None
    priority: str | None = None
    url: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkItemResult:
    """Result of a work item operation."""

    ok: bool
    item: WorkItem | None = None
    items: list[WorkItem] = field(default_factory=list)
    error: str | None = None
    raw_response: Any = None


class WorkItemAdapter(ABC):
    """
    Base adapter for work item/ticket systems.

    Subclasses implement provider-specific operations (Notion, Linear, Jira, etc.).
    """

    adapter_name: str = "base"

    def __init__(self, config: dict[str, Any]) -> None:
        """
        Initialize adapter with provider-specific configuration.

        Args:
            config: Provider config from ai-team.repo.json work_item_source.
        """
        self.config = config

    @abstractmethod
    def create(self, item: WorkItem) -> WorkItemResult:
        """
        Create a new work item.

        Args:
            item: WorkItem with title, description, status, priority.

        Returns:
            WorkItemResult with the created item (including ID).
        """
        ...

    @abstractmethod
    def update(self, item: WorkItem) -> WorkItemResult:
        """
        Update an existing work item.

        Args:
            item: WorkItem with id and fields to update.

        Returns:
            WorkItemResult with the updated item.
        """
        ...

    @abstractmethod
    def get(self, item_id: str) -> WorkItemResult:
        """
        Get a work item by ID.

        Args:
            item_id: The item's unique identifier.

        Returns:
            WorkItemResult with the item.
        """
        ...

    @abstractmethod
    def list(
        self,
        status: str | None = None,
        limit: int = 50,
    ) -> WorkItemResult:
        """
        List work items, optionally filtered by status.

        Args:
            status: Filter by status (e.g., "Backlog", "In progress").
            limit: Maximum number of items to return.

        Returns:
            WorkItemResult with items list.
        """
        ...

    def get_field_name(self, mat_field: str) -> str:
        """
        Map MAT field name to provider-specific field name.

        Uses field_map from config if available, otherwise returns defaults.
        """
        defaults = {
            "title": "Name",
            "status": "Status",
            "priority": "Priority",
            "description": "Description",
            "ticket_id": "ID",
        }
        field_map = self.config.get("field_map", {})
        return field_map.get(mat_field, defaults.get(mat_field, mat_field))
