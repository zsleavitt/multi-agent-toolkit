"""Factory for creating close adapters from ai-team.repo.json config."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from lib.skills.finish_branch.adapters.base import CloseAdapter, CloseResult
from lib.skills.finish_branch.adapters.github_issues import GitHubIssuesCloseAdapter
from lib.skills.finish_branch.adapters.jira import JiraCloseAdapter
from lib.skills.finish_branch.adapters.notion import NotionCloseAdapter
from lib.skills.finish_branch.adapters.noop import NoopCloseAdapter


def get_close_adapter(repo_root: Path | str) -> CloseAdapter:
    """
    Create a close adapter based on ai-team.repo.json configuration.

    Args:
        repo_root: Path to repository root.

    Returns:
        Appropriate CloseAdapter instance.

    Raises:
        FileNotFoundError: If ai-team.repo.json not found.
    """
    repo_root = Path(repo_root)
    config_path = repo_root / "ai-team.repo.json"

    if not config_path.exists():
        raise FileNotFoundError(f"ai-team.repo.json not found at {config_path}")

    config = json.loads(config_path.read_text())
    work_item_source = config.get("work_item_source", {})
    adapter_type = work_item_source.get("adapter", "none")

    if adapter_type == "github_issues":
        adapter_config = work_item_source.get("github_issues", {})
        return GitHubIssuesCloseAdapter(adapter_config)

    elif adapter_type == "jira":
        adapter_config = work_item_source.get("jira", {})
        return JiraCloseAdapter(adapter_config)

    elif adapter_type == "notion":
        adapter_config = work_item_source.get("notion", {})
        return NotionCloseAdapter(adapter_config)

    elif adapter_type in ("file", "none"):
        return NoopCloseAdapter({}, source_type=adapter_type)

    else:
        # Unknown/unsupported adapter type - raise error instead of silently succeeding
        supported = ["github_issues", "jira", "notion", "file", "none"]
        raise ValueError(
            f"Unsupported work_item_source adapter: '{adapter_type}'. "
            f"Supported adapters: {', '.join(supported)}"
        )
