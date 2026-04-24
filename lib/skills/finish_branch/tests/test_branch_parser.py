"""Tests for branch name parsing."""

from __future__ import annotations

import pytest

from lib.skills.finish_branch.branch_parser import extract_work_item_ref


class TestExtractWorkItemRef:
    """Tests for extract_work_item_ref function."""

    def test_extracts_mat_from_feature_branch(self) -> None:
        """Extract MAT-XX from standard feature branch."""
        assert extract_work_item_ref("feat/mat-42-crew-schema") == "MAT-42"

    def test_extracts_mat_from_fix_branch(self) -> None:
        """Extract MAT-XX from fix branch."""
        assert extract_work_item_ref("fix/mat-15-bug-fix") == "MAT-15"

    def test_extracts_mat_uppercase(self) -> None:
        """Extract MAT-XX when already uppercase."""
        assert extract_work_item_ref("feat/MAT-42-crew-schema") == "MAT-42"

    def test_extracts_mat_with_multiple_numbers(self) -> None:
        """Extract first MAT-XX when multiple numbers in branch."""
        assert extract_work_item_ref("feat/mat-42-add-v2-support") == "MAT-42"

    def test_extracts_mat_at_end(self) -> None:
        """Extract MAT-XX when at end of branch name."""
        assert extract_work_item_ref("chore/cleanup-mat-99") == "MAT-99"

    def test_returns_none_for_no_mat(self) -> None:
        """Return None when no MAT-XX pattern found."""
        assert extract_work_item_ref("feat/add-new-feature") is None

    def test_returns_none_for_empty(self) -> None:
        """Return None for empty branch name."""
        assert extract_work_item_ref("") is None

    def test_returns_none_for_main(self) -> None:
        """Return None for main/master branches."""
        assert extract_work_item_ref("main") is None
        assert extract_work_item_ref("master") is None

    def test_extracts_jira_style(self) -> None:
        """Extract PROJ-123 style refs."""
        assert extract_work_item_ref("feat/PROJ-123-add-feature") == "PROJ-123"

    def test_case_insensitive_prefix(self) -> None:
        """Handle case variations in prefix."""
        assert extract_work_item_ref("feat/Mat-42-test") == "MAT-42"
