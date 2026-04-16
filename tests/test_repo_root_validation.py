#!/usr/bin/env python3
"""Tests for repo_root path validation pattern (MAT-23).

Ensures the schema pattern correctly accepts:
- Unix absolute paths: /path/to/repo
- Tilde expansion paths: ~/repo, ~user/repo
- Windows absolute paths: C:\repo, D:/repo

And rejects:
- Relative paths: ./repo, ../repo, repo/path
- Traversal attempts: ../../etc
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

SCHEMAS = [
    ROOT / "schemas" / "gemini-git-ops" / "v1" / "request.schema.json",
    ROOT / "schemas" / "codex-code-exec" / "v1" / "request.schema.json",
]


def _extract_repo_root_pattern(schema_path: Path) -> str:
    """Extract the repo_root pattern from a schema file."""
    data = json.loads(schema_path.read_text(encoding="utf-8"))
    return data["$defs"]["repo_root"]["pattern"]


@pytest.fixture(params=SCHEMAS, ids=["MAT-1", "MAT-2"])
def repo_root_pattern(request) -> re.Pattern:
    """Fixture providing compiled regex from each schema."""
    pattern_str = _extract_repo_root_pattern(request.param)
    return re.compile(pattern_str)


class TestValidPaths:
    """Test cases for paths that MUST be accepted."""

    @pytest.mark.parametrize(
        "path",
        [
            "/tmp/repo",
            "/home/user/projects/app",
            "/",
            "/Users/zach.leavitt/guideline/app",
            "/var/lib/data",
        ],
        ids=["tmp", "nested", "root", "macos-home", "var"],
    )
    def test_unix_absolute(self, repo_root_pattern, path):
        """Unix absolute paths starting with / should be valid."""
        assert repo_root_pattern.match(path), f"Expected {path} to match"

    @pytest.mark.parametrize(
        "path",
        [
            "~/repo",
            "~/guideline/app",
            "~/.claude/multi-agent-toolkit",
            "~/",
        ],
        ids=["simple", "nested", "dotdir", "home-only"],
    )
    def test_tilde_home(self, repo_root_pattern, path):
        """Tilde paths for home directory should be valid."""
        assert repo_root_pattern.match(path), f"Expected {path} to match"

    @pytest.mark.parametrize(
        "path",
        [
            "~zach/projects",
            "~developer/repos/api",
            "~user123/code",
        ],
        ids=["zach", "developer", "user123"],
    )
    def test_tilde_user(self, repo_root_pattern, path):
        """Tilde paths with username (~user/) should be valid."""
        assert repo_root_pattern.match(path), f"Expected {path} to match"

    @pytest.mark.parametrize(
        "path",
        [
            "C:\\Users\\dev\\repo",
            "C:/Users/dev/repo",
            "D:\\projects",
            "Z:/backups/code",
        ],
        ids=["backslash", "forward", "d-drive", "z-drive"],
    )
    def test_windows_drive(self, repo_root_pattern, path):
        """Windows drive letter paths should be valid."""
        assert repo_root_pattern.match(path), f"Expected {path} to match"


class TestInvalidPaths:
    """Test cases for paths that MUST be rejected."""

    @pytest.mark.parametrize(
        "path",
        [
            "./repo",
            "../repo",
            "repo/path",
            "relative/path/here",
            ".",
            "..",
        ],
        ids=["dot-slash", "dot-dot", "bare", "nested-relative", "dot", "dotdot"],
    )
    def test_relative_paths(self, repo_root_pattern, path):
        """Relative paths should be rejected."""
        assert not repo_root_pattern.match(path), f"Expected {path} to NOT match"

    @pytest.mark.parametrize(
        "path",
        [
            "../../sensitive",
            "../../../etc/passwd",
            "foo/../../../bar",
        ],
        ids=["double-dot", "etc-passwd", "embedded-traversal"],
    )
    def test_traversal_attempts(self, repo_root_pattern, path):
        """Traversal attempts should be rejected at schema level."""
        assert not repo_root_pattern.match(path), f"Expected {path} to NOT match"

    @pytest.mark.parametrize(
        "path",
        [
            "",
            " /repo",
            "file:///repo",
            "https://example.com/repo",
        ],
        ids=["empty", "leading-space", "file-uri", "https-url"],
    )
    def test_malformed_paths(self, repo_root_pattern, path):
        """Malformed or URI-style paths should be rejected."""
        assert not repo_root_pattern.match(path), f"Expected {path} to NOT match"


class TestPatternConsistency:
    """Ensure both MAT-1 and MAT-2 use identical patterns."""

    def test_patterns_match(self):
        """MAT-1 and MAT-2 repo_root patterns must be identical."""
        patterns = [_extract_repo_root_pattern(s) for s in SCHEMAS]
        assert len(set(patterns)) == 1, f"Patterns differ: {patterns}"
