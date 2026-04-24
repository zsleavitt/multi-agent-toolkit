"""No-op adapter for file and none work item sources."""

from __future__ import annotations

from typing import Any

from lib.skills.finish_branch.adapters.base import CloseResult


class NoopCloseAdapter:
    """
    No-op adapter for 'file' and 'none' work item sources.

    Returns informational message without taking action.
    """

    adapter_name = "noop"

    def __init__(self, config: dict[str, Any], source_type: str = "none") -> None:
        self.config = config
        self.source_type = source_type

    def close(self, work_item_ref: str, comment: str | None = None) -> CloseResult:
        """
        No-op close - just returns informational message.

        Args:
            work_item_ref: Work item reference (ignored).
            comment: Optional comment (ignored).

        Returns:
            CloseResult with informational message.
        """
        if self.source_type == "none":
            return CloseResult(
                ok=True,
                message=f"No work item system configured. Skipping close for {work_item_ref}.",
            )
        else:  # file
            return CloseResult(
                ok=True,
                message=f"File-based work items do not support auto-close. Manual update needed for {work_item_ref}.",
            )
