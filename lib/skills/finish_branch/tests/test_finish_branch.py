"""Tests for finish-branch skill."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lib.skills.finish_branch.adapter_factory import get_close_adapter
from lib.skills.finish_branch.adapters.github_issues import GitHubIssuesCloseAdapter
from lib.skills.finish_branch.adapters.jira import JiraCloseAdapter
from lib.skills.finish_branch.adapters.notion import NotionCloseAdapter
from lib.skills.finish_branch.adapters.noop import NoopCloseAdapter


class TestGetCloseAdapter:
    """Tests for adapter factory."""

    def test_returns_github_adapter(self, tmp_path: Path) -> None:
        """Return GitHubIssuesCloseAdapter for github_issues config."""
        config = {
            "work_item_source": {
                "adapter": "github_issues",
                "github_issues": {
                    "owner": "testowner",
                    "repo": "testrepo",
                },
            },
        }
        (tmp_path / "ai-team.repo.json").write_text(json.dumps(config))

        adapter = get_close_adapter(tmp_path)

        assert isinstance(adapter, GitHubIssuesCloseAdapter)
        assert adapter.owner == "testowner"
        assert adapter.repo == "testrepo"

    def test_returns_jira_adapter(self, tmp_path: Path) -> None:
        """Return JiraCloseAdapter for jira config."""
        config = {
            "work_item_source": {
                "adapter": "jira",
                "jira": {
                    "base_url": "https://example.atlassian.net",
                    "project_key": "TEST",
                },
            },
        }
        (tmp_path / "ai-team.repo.json").write_text(json.dumps(config))

        adapter = get_close_adapter(tmp_path)

        assert isinstance(adapter, JiraCloseAdapter)
        assert adapter.base_url == "https://example.atlassian.net"
        assert adapter.project_key == "TEST"

    def test_returns_notion_adapter(self, tmp_path: Path) -> None:
        """Return NotionCloseAdapter for notion config."""
        config = {
            "work_item_source": {
                "adapter": "notion",
                "notion": {
                    "database_id": "abc123",
                    "status_property": "Status",
                },
            },
        }
        (tmp_path / "ai-team.repo.json").write_text(json.dumps(config))

        adapter = get_close_adapter(tmp_path)

        assert isinstance(adapter, NotionCloseAdapter)
        assert adapter.database_id == "abc123"
        assert adapter.status_property == "Status"

    def test_returns_noop_for_none(self, tmp_path: Path) -> None:
        """Return NoopCloseAdapter for none config."""
        config = {
            "work_item_source": {
                "adapter": "none",
            },
        }
        (tmp_path / "ai-team.repo.json").write_text(json.dumps(config))

        adapter = get_close_adapter(tmp_path)

        assert isinstance(adapter, NoopCloseAdapter)
        assert adapter.source_type == "none"

    def test_returns_noop_for_file(self, tmp_path: Path) -> None:
        """Return NoopCloseAdapter for file config."""
        config = {
            "work_item_source": {
                "adapter": "file",
            },
        }
        (tmp_path / "ai-team.repo.json").write_text(json.dumps(config))

        adapter = get_close_adapter(tmp_path)

        assert isinstance(adapter, NoopCloseAdapter)
        assert adapter.source_type == "file"

    def test_raises_for_unknown_adapter(self, tmp_path: Path) -> None:
        """Raise ValueError for unknown/unsupported adapter type."""
        config = {
            "work_item_source": {
                "adapter": "unknown_system",
            },
        }
        (tmp_path / "ai-team.repo.json").write_text(json.dumps(config))

        with pytest.raises(ValueError, match="Unsupported work_item_source adapter"):
            get_close_adapter(tmp_path)

    def test_raises_for_linear_adapter(self, tmp_path: Path) -> None:
        """Raise ValueError for linear adapter (valid in MAT-9 but not implemented)."""
        config = {
            "work_item_source": {
                "adapter": "linear",
            },
        }
        (tmp_path / "ai-team.repo.json").write_text(json.dumps(config))

        with pytest.raises(ValueError, match="Unsupported work_item_source adapter: 'linear'"):
            get_close_adapter(tmp_path)

    def test_returns_noop_for_missing_work_item_source(self, tmp_path: Path) -> None:
        """Return NoopCloseAdapter when work_item_source is missing."""
        config = {}
        (tmp_path / "ai-team.repo.json").write_text(json.dumps(config))

        adapter = get_close_adapter(tmp_path)

        assert isinstance(adapter, NoopCloseAdapter)
        assert adapter.source_type == "none"

    def test_raises_for_missing_config(self, tmp_path: Path) -> None:
        """Raise FileNotFoundError when config missing."""
        with pytest.raises(FileNotFoundError):
            get_close_adapter(tmp_path)

    def test_accepts_string_path(self, tmp_path: Path) -> None:
        """Accept string path in addition to Path object."""
        config = {
            "work_item_source": {
                "adapter": "none",
            },
        }
        (tmp_path / "ai-team.repo.json").write_text(json.dumps(config))

        adapter = get_close_adapter(str(tmp_path))

        assert isinstance(adapter, NoopCloseAdapter)
