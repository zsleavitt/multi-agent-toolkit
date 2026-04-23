"""Base types for work item close adapters."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class CloseResult:
    """Result of closing/transitioning a work item."""

    ok: bool
    message: str
    item_id: str | None = None
    item_url: str | None = None
    error: str | None = None


class CloseAdapter(Protocol):
    """Protocol for work item close adapters."""

    adapter_name: str

    def close(self, work_item_ref: str, comment: str | None = None) -> CloseResult:
        """
        Close or transition a work item.

        Args:
            work_item_ref: The work item reference (e.g., "MAT-42").
            comment: Optional comment to add when closing.

        Returns:
            CloseResult indicating success or failure.
        """
        ...
