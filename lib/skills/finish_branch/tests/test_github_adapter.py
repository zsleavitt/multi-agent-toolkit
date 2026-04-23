"""Tests for GitHub Issues close adapter."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from lib.skills.finish_branch.adapters.github_issues import GitHubIssuesCloseAdapter


@pytest.fixture
def adapter() -> GitHubIssuesCloseAdapter:
    """Create adapter with test config."""
    return GitHubIssuesCloseAdapter(
        config={
            "owner": "testowner",
            "repo": "testrepo",
        }
    )


class TestGitHubIssuesCloseAdapter:
    """Tests for GitHubIssuesCloseAdapter."""

    def test_adapter_name(self, adapter: GitHubIssuesCloseAdapter) -> None:
        """Adapter has correct name."""
        assert adapter.adapter_name == "github_issues"

    def test_close_success(self, adapter: GitHubIssuesCloseAdapter) -> None:
        """Successfully close an issue."""
        with patch("subprocess.run") as mock_run:
            # First call: gh issue list --search
            mock_list = MagicMock()
            mock_list.returncode = 0
            mock_list.stdout = '[{"number": 42, "title": "MAT-42: Test issue", "url": "https://github.com/testowner/testrepo/issues/42"}]'

            # Second call: gh issue close
            mock_close = MagicMock()
            mock_close.returncode = 0
            mock_close.stdout = ""

            mock_run.side_effect = [mock_list, mock_close]

            result = adapter.close("MAT-42")

        assert result.ok
        assert result.item_id == "42"
        assert "MAT-42" in result.message

    def test_close_issue_not_found(self, adapter: GitHubIssuesCloseAdapter) -> None:
        """Handle case when issue not found."""
        with patch("subprocess.run") as mock_run:
            mock_list = MagicMock()
            mock_list.returncode = 0
            mock_list.stdout = "[]"

            mock_run.return_value = mock_list

            result = adapter.close("MAT-999")

        assert not result.ok
        assert "not found" in result.error.lower()

    def test_close_with_comment(self, adapter: GitHubIssuesCloseAdapter) -> None:
        """Close with a comment."""
        with patch("subprocess.run") as mock_run:
            mock_list = MagicMock()
            mock_list.returncode = 0
            mock_list.stdout = '[{"number": 42, "title": "MAT-42: Test", "url": "https://example.com/42"}]'

            mock_close = MagicMock()
            mock_close.returncode = 0

            mock_run.side_effect = [mock_list, mock_close]

            result = adapter.close("MAT-42", comment="Merged in PR #100")

        assert result.ok
        # Check that close was called with --comment flag
        close_call = mock_run.call_args_list[1]
        assert "--comment" in close_call[0][0]

    def test_close_gh_command_fails(self, adapter: GitHubIssuesCloseAdapter) -> None:
        """Handle gh command failure."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError("gh not found")

            result = adapter.close("MAT-42")

        assert not result.ok
        assert "gh" in result.error.lower()

    def test_close_gh_timeout(self, adapter: GitHubIssuesCloseAdapter) -> None:
        """Handle gh command timeout."""
        from subprocess import TimeoutExpired

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = TimeoutExpired(cmd="gh", timeout=30)

            result = adapter.close("MAT-42")

        assert not result.ok
        assert "timed out" in result.error.lower()
