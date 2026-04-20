"""Tests for GitHub Issues adapter."""

import pytest

from mat_runtime.work_items.base import WorkItem
from mat_runtime.work_items.github_issues import GitHubIssuesAdapter


@pytest.fixture
def adapter():
    """Create a GitHub Issues adapter with test config."""
    return GitHubIssuesAdapter(
        {
            "owner": "test-owner",
            "repo": "test-repo",
        }
    )


@pytest.fixture
def adapter_custom_labels():
    """Create adapter with custom priority labels."""
    return GitHubIssuesAdapter(
        {
            "owner": "test-owner",
            "repo": "test-repo",
            "priority_labels": {
                "P0": "urgent",
                "P1": "high",
                "P2": "medium",
            },
        }
    )


class TestBuildCreatePayload:
    def test_basic_create(self, adapter):
        item = WorkItem(title="Test issue")
        payload = adapter.build_create_payload(item)

        assert payload["method"] == "create"
        assert payload["owner"] == "test-owner"
        assert payload["repo"] == "test-repo"
        assert payload["title"] == "Test issue"
        assert "body" not in payload
        assert "labels" not in payload

    def test_create_with_description(self, adapter):
        item = WorkItem(title="Test issue", description="Test description")
        payload = adapter.build_create_payload(item)

        assert payload["body"] == "Test description"

    def test_create_with_priority(self, adapter):
        item = WorkItem(title="Test issue", priority="P1")
        payload = adapter.build_create_payload(item)

        assert payload["labels"] == ["priority:high"]
        assert "**Priority:** P1" in payload["body"]

    def test_create_with_status_and_priority(self, adapter):
        item = WorkItem(
            title="Test issue",
            status="In progress",
            priority="P0",
            description="Some work",
        )
        payload = adapter.build_create_payload(item)

        assert "**Priority:** P0" in payload["body"]
        assert "**Status:** In progress" in payload["body"]
        assert "Some work" in payload["body"]
        assert payload["labels"] == ["priority:critical"]

    def test_create_with_custom_labels(self, adapter_custom_labels):
        item = WorkItem(title="Test", priority="P1")
        payload = adapter_custom_labels.build_create_payload(item)

        assert payload["labels"] == ["high"]


class TestBuildUpdatePayload:
    def test_update_status_to_done(self, adapter):
        item = WorkItem(id="42", status="Done")
        payload = adapter.build_update_payload(item)

        assert payload["method"] == "update"
        assert payload["issue_number"] == 42
        assert payload["state"] == "closed"
        assert payload["state_reason"] == "completed"

    def test_update_status_to_open(self, adapter):
        item = WorkItem(id="42", status="In progress")
        payload = adapter.build_update_payload(item)

        assert payload["state"] == "open"
        assert "state_reason" not in payload

    def test_update_priority(self, adapter):
        item = WorkItem(id="42", priority="P2")
        payload = adapter.build_update_payload(item)

        assert payload["labels"] == ["priority:medium"]


class TestBuildQuery:
    def test_list_all(self, adapter):
        payload = adapter.build_query()

        assert payload["owner"] == "test-owner"
        assert payload["repo"] == "test-repo"
        assert payload["perPage"] == 50
        assert "state" not in payload

    def test_list_with_status(self, adapter):
        payload = adapter.build_query(status="Done")

        assert payload["state"] == "CLOSED"

    def test_list_with_limit(self, adapter):
        payload = adapter.build_query(limit=10)

        assert payload["perPage"] == 10

    def test_list_limit_capped_at_100(self, adapter):
        payload = adapter.build_query(limit=200)

        assert payload["perPage"] == 100


class TestParseGitHubIssue:
    def test_parse_basic_issue(self, adapter):
        issue = {
            "number": 42,
            "title": "Test issue",
            "body": "Test body",
            "state": "OPEN",
            "url": "https://github.com/test-owner/test-repo/issues/42",
            "labels": [],
        }
        item = adapter.parse_github_issue(issue)

        assert item.id == "42"
        assert item.ticket_id == 42
        assert item.title == "Test issue"
        assert item.description == "Test body"
        assert item.status == "Backlog"
        assert item.priority is None
        assert item.url == "https://github.com/test-owner/test-repo/issues/42"

    def test_parse_closed_issue(self, adapter):
        issue = {"number": 1, "title": "Done", "state": "CLOSED", "labels": []}
        item = adapter.parse_github_issue(issue)

        assert item.status == "Done"

    def test_parse_issue_with_priority_label(self, adapter):
        issue = {
            "number": 1,
            "title": "Urgent",
            "state": "OPEN",
            "labels": [{"name": "priority:critical"}, {"name": "bug"}],
        }
        item = adapter.parse_github_issue(issue)

        assert item.priority == "P0"
        assert "priority:critical" in item.metadata["labels"]
        assert "bug" in item.metadata["labels"]

    def test_parse_issue_with_string_labels(self, adapter):
        # Some API responses may have string labels instead of dicts
        issue = {
            "number": 1,
            "title": "Test",
            "state": "OPEN",
            "labels": ["priority:high", "enhancement"],
        }
        item = adapter.parse_github_issue(issue)

        assert item.priority == "P1"


class TestParseGitHubResults:
    def test_parse_multiple_issues(self, adapter):
        issues = [
            {"number": 1, "title": "First", "state": "OPEN", "labels": []},
            {"number": 2, "title": "Second", "state": "CLOSED", "labels": []},
        ]
        items = adapter.parse_github_results(issues)

        assert len(items) == 2
        assert items[0].title == "First"
        assert items[1].title == "Second"
