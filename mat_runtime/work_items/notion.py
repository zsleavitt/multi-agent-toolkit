"""Notion work item adapter.

This adapter provides the interface and configuration for Notion ticket management.
Actual MCP tool calls are made by the /ticket skill in the orchestrator context.

The adapter handles:
- Field mapping between MAT fields and Notion properties
- Building queries and page creation payloads
- Parsing Notion responses into WorkItem objects

Usage from /ticket skill:
    adapter = get_adapter_from_profile(repo_root)
    # adapter.build_create_payload(item) -> dict for notion-create-pages
    # adapter.build_query(status) -> dict for notion-query-data-sources
    # adapter.parse_notion_row(row) -> WorkItem
"""

from __future__ import annotations

from typing import Any

from mat_runtime.work_items.base import WorkItem, WorkItemAdapter, WorkItemResult
from mat_runtime.work_items.registry import register_adapter


@register_adapter("notion")
class NotionAdapter(WorkItemAdapter):
    """
    Notion database adapter for work items.

    Configuration (from ai-team.repo.json):
        - database_id: Notion database UUID
        - data_source_id: Optional data source UUID for multi-source DBs
        - field_map: Mapping of MAT fields to Notion property names
    """

    adapter_name = "notion"

    # MCP tool names for Notion operations
    MCP_TOOL_CREATE = "notion-create-pages"
    MCP_TOOL_UPDATE = "notion-update-page"
    MCP_TOOL_QUERY = "notion-query-data-sources"
    MCP_TOOL_FETCH = "notion-fetch"

    # Default field mappings for Notion
    DEFAULT_FIELD_MAP = {
        "title": "Name",
        "status": "Status",
        "priority": "Priority",
        "description": "Acceptance criteria",
        "ticket_id": "Ticket",
    }

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        self.database_id = config.get("database_id", "")
        self.data_source_id = config.get("data_source_id")
        self._field_map = {**self.DEFAULT_FIELD_MAP, **config.get("field_map", {})}

    @property
    def data_source_url(self) -> str:
        """Get the collection:// URL for queries."""
        ds_id = self.data_source_id or self.database_id
        return f"collection://{ds_id}"

    def get_field_name(self, mat_field: str) -> str:
        """Map MAT field name to Notion property name."""
        return self._field_map.get(mat_field, mat_field)

    def build_create_payload(self, item: WorkItem) -> dict[str, Any]:
        """
        Build payload for notion-create-pages MCP tool.

        Returns dict with 'properties' and optional 'content' keys.
        """
        properties: dict[str, Any] = {}

        if item.title:
            properties[self.get_field_name("title")] = item.title

        if item.status:
            properties[self.get_field_name("status")] = item.status

        if item.priority:
            properties[self.get_field_name("priority")] = item.priority

        if item.description:
            properties[self.get_field_name("description")] = item.description

        return {
            "properties": properties,
            "content": item.metadata.get("content", ""),
        }

    def build_update_payload(self, item: WorkItem) -> dict[str, Any]:
        """
        Build payload for notion-update-page MCP tool.

        Returns dict with 'page_id', 'command', and 'properties' keys.
        """
        properties: dict[str, Any] = {}

        if item.title:
            properties[self.get_field_name("title")] = item.title

        if item.status:
            properties[self.get_field_name("status")] = item.status

        if item.priority:
            properties[self.get_field_name("priority")] = item.priority

        if item.description:
            properties[self.get_field_name("description")] = item.description

        return {
            "page_id": item.id,
            "command": "update_properties",
            "properties": properties,
        }

    def build_query(
        self,
        status: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        """
        Build payload for notion-query-data-sources MCP tool.

        Returns dict with 'data' key containing SQL query.
        """
        title_field = self.get_field_name("title")
        status_field = self.get_field_name("status")
        priority_field = self.get_field_name("priority")
        ticket_field = self.get_field_name("ticket_id")

        # Build SELECT clause
        fields = [ticket_field, title_field, status_field, priority_field, "url"]
        select = ", ".join(f'"{f}"' for f in fields)

        # Build WHERE clause
        where = ""
        params = []
        if status:
            where = f'WHERE "{status_field}" = ?'
            params.append(status)

        query = f'SELECT {select} FROM "{self.data_source_url}" {where} ORDER BY "{ticket_field}" ASC LIMIT {limit}'

        return {
            "data": {
                "data_source_urls": [self.data_source_url],
                "query": query,
                "params": params,
            }
        }

    def parse_notion_row(self, row: dict[str, Any]) -> WorkItem:
        """Parse a Notion query result row into a WorkItem."""
        url = row.get("url") or ""
        return WorkItem(
            id=url.split("/")[-1] if url else None,
            ticket_id=row.get(self.get_field_name("ticket_id")),
            title=row.get(self.get_field_name("title"), ""),
            status=row.get(self.get_field_name("status")),
            priority=row.get(self.get_field_name("priority")),
            url=row.get("url"),
            description=row.get(self.get_field_name("description"), ""),
        )

    def parse_notion_results(self, results: list[dict[str, Any]]) -> list[WorkItem]:
        """Parse multiple Notion query result rows into WorkItems."""
        return [self.parse_notion_row(row) for row in results]

    # Abstract method implementations (for direct use - not typical for Notion)
    # These return "not implemented" results since actual calls go through MCP

    def create(self, item: WorkItem) -> WorkItemResult:
        """
        Create requires MCP context. Use build_create_payload() instead.

        The /ticket skill should:
        1. Call adapter.build_create_payload(item)
        2. Call notion-create-pages MCP tool with the payload
        3. Parse the response
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
        Get requires MCP context. Use notion-fetch MCP tool directly.
        """
        return WorkItemResult(
            ok=False,
            error="Direct get not supported. Use notion-fetch MCP tool.",
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
