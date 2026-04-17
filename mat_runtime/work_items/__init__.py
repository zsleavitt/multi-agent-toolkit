"""Work item adapters for ticket systems (Notion, Linear, Jira, GitHub Issues)."""

from mat_runtime.work_items.base import WorkItem, WorkItemAdapter, WorkItemResult
from mat_runtime.work_items.registry import (
    get_adapter,
    get_adapter_from_profile,
    register_adapter,
)

__all__ = [
    "WorkItem",
    "WorkItemAdapter",
    "WorkItemResult",
    "get_adapter",
    "get_adapter_from_profile",
    "register_adapter",
]
