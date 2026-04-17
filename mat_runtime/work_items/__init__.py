"""Work item adapters for ticket systems (Notion, Linear, Jira, GitHub Issues)."""

from mat_runtime.work_items.base import WorkItem, WorkItemAdapter, WorkItemResult
from mat_runtime.work_items.registry import get_adapter, register_adapter

__all__ = [
    "WorkItem",
    "WorkItemAdapter",
    "WorkItemResult",
    "get_adapter",
    "register_adapter",
]
