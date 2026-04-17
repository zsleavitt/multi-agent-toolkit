"""Tests for Notion work item adapter."""

from __future__ import annotations

import pytest

from mat_runtime.work_items.base import WorkItem
from mat_runtime.work_items.notion import NotionAdapter
from mat_runtime.work_items.registry import get_adapter, get_adapter_from_profile


class TestNotionAdapter:
    """Tests for NotionAdapter."""

    @pytest.fixture
    def config(self) -> dict:
        return {
            "database_id": "c54de570-f4ec-4335-87b7-cac957b950c1",
            "data_source_id": "72b0d1fc-88af-4986-ad73-5324a3696ac3",
            "field_map": {
                "title": "Name",
                "status": "Status",
                "priority": "Priority",
                "description": "Acceptance criteria",
                "ticket_id": "Ticket",
            },
        }

    @pytest.fixture
    def adapter(self, config: dict) -> NotionAdapter:
        return NotionAdapter(config)

    def test_data_source_url(self, adapter: NotionAdapter) -> None:
        assert adapter.data_source_url == "collection://72b0d1fc-88af-4986-ad73-5324a3696ac3"

    def test_data_source_url_fallback(self) -> None:
        # When data_source_id is missing, use database_id
        adapter = NotionAdapter({"database_id": "abc123"})
        assert adapter.data_source_url == "collection://abc123"

    def test_get_field_name_mapped(self, adapter: NotionAdapter) -> None:
        assert adapter.get_field_name("title") == "Name"
        assert adapter.get_field_name("status") == "Status"
        assert adapter.get_field_name("description") == "Acceptance criteria"

    def test_get_field_name_unmapped(self, adapter: NotionAdapter) -> None:
        # Unmapped fields return as-is
        assert adapter.get_field_name("custom_field") == "custom_field"

    def test_build_create_payload(self, adapter: NotionAdapter) -> None:
        item = WorkItem(
            title="Test ticket",
            description="Test description",
            status="Backlog",
            priority="P1",
        )

        payload = adapter.build_create_payload(item)

        assert payload["properties"]["Name"] == "Test ticket"
        assert payload["properties"]["Status"] == "Backlog"
        assert payload["properties"]["Priority"] == "P1"
        assert payload["properties"]["Acceptance criteria"] == "Test description"

    def test_build_create_payload_partial(self, adapter: NotionAdapter) -> None:
        item = WorkItem(title="Minimal ticket")

        payload = adapter.build_create_payload(item)

        assert payload["properties"]["Name"] == "Minimal ticket"
        assert "Status" not in payload["properties"]

    def test_build_update_payload(self, adapter: NotionAdapter) -> None:
        item = WorkItem(
            id="page-uuid-123",
            status="Done",
        )

        payload = adapter.build_update_payload(item)

        assert payload["page_id"] == "page-uuid-123"
        assert payload["command"] == "update_properties"
        assert payload["properties"]["Status"] == "Done"

    def test_build_query_no_filter(self, adapter: NotionAdapter) -> None:
        payload = adapter.build_query()

        assert "data" in payload
        assert payload["data"]["data_source_urls"] == [adapter.data_source_url]
        assert "SELECT" in payload["data"]["query"]
        assert "WHERE" not in payload["data"]["query"]
        assert payload["data"]["params"] == []

    def test_build_query_with_status_filter(self, adapter: NotionAdapter) -> None:
        payload = adapter.build_query(status="Backlog")

        assert 'WHERE "Status" = ?' in payload["data"]["query"]
        assert payload["data"]["params"] == ["Backlog"]

    def test_build_query_with_limit(self, adapter: NotionAdapter) -> None:
        payload = adapter.build_query(limit=10)

        assert "LIMIT 10" in payload["data"]["query"]

    def test_parse_notion_row(self, adapter: NotionAdapter) -> None:
        row = {
            "Ticket": 42,
            "Name": "Test ticket",
            "Status": "In progress",
            "Priority": "P0",
            "url": "https://notion.so/page-uuid-123",
        }

        item = adapter.parse_notion_row(row)

        assert item.ticket_id == 42
        assert item.title == "Test ticket"
        assert item.status == "In progress"
        assert item.priority == "P0"
        assert item.id == "page-uuid-123"

    def test_parse_notion_results(self, adapter: NotionAdapter) -> None:
        rows = [
            {"Ticket": 1, "Name": "First", "Status": "Done"},
            {"Ticket": 2, "Name": "Second", "Status": "Backlog"},
        ]

        items = adapter.parse_notion_results(rows)

        assert len(items) == 2
        assert items[0].title == "First"
        assert items[1].title == "Second"


class TestRegistry:
    """Tests for adapter registry."""

    def test_get_adapter_notion(self) -> None:
        adapter = get_adapter("notion", {"database_id": "test"})
        assert isinstance(adapter, NotionAdapter)

    def test_get_adapter_unknown(self) -> None:
        with pytest.raises(ValueError, match="Unknown work item adapter"):
            get_adapter("unknown", {})

    def test_get_adapter_from_profile(self, tmp_path) -> None:
        # Create a test profile
        profile = {
            "schema_version": "1.0.0",
            "identity": {"id": "test"},
            "repo": {"default_branch": "main"},
            "work_item_source": {
                "adapter": "notion",
                "notion": {"database_id": "test-db"},
            },
        }
        profile_path = tmp_path / "ai-team.repo.json"
        import json

        profile_path.write_text(json.dumps(profile))

        adapter = get_adapter_from_profile(tmp_path)

        assert isinstance(adapter, NotionAdapter)
        assert adapter.database_id == "test-db"

    def test_get_adapter_from_profile_none(self, tmp_path) -> None:
        # Profile with adapter: none
        profile = {
            "schema_version": "1.0.0",
            "identity": {"id": "test"},
            "repo": {"default_branch": "main"},
            "work_item_source": {"adapter": "none"},
        }
        profile_path = tmp_path / "ai-team.repo.json"
        import json

        profile_path.write_text(json.dumps(profile))

        adapter = get_adapter_from_profile(tmp_path)

        assert adapter is None

    def test_get_adapter_from_profile_not_found(self, tmp_path) -> None:
        with pytest.raises(FileNotFoundError):
            get_adapter_from_profile(tmp_path)
