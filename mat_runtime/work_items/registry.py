"""Registry for work item adapters."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from mat_runtime.work_items.base import WorkItemAdapter

# Registry of adapter name -> adapter class
_ADAPTERS: dict[str, type[WorkItemAdapter]] = {}


def register_adapter(name: str):
    """Decorator to register an adapter class."""

    def decorator(cls: type[WorkItemAdapter]):
        _ADAPTERS[name] = cls
        cls.adapter_name = name
        return cls

    return decorator


def get_adapter(
    adapter_name: str,
    config: dict[str, Any],
) -> WorkItemAdapter:
    """
    Get an adapter instance by name.

    Args:
        adapter_name: Adapter name (e.g., "notion", "linear", "jira").
        config: Provider-specific configuration.

    Returns:
        Initialized adapter instance.

    Raises:
        ValueError: If adapter is not registered.
    """
    # Lazy import adapters to register them
    _ensure_adapters_loaded()

    if adapter_name not in _ADAPTERS:
        available = ", ".join(sorted(_ADAPTERS.keys()))
        raise ValueError(
            f"Unknown work item adapter: {adapter_name}. Available: {available}"
        )

    return _ADAPTERS[adapter_name](config)


def get_adapter_from_profile(
    repo_root: Path | str | None = None,
) -> WorkItemAdapter | None:
    """
    Load adapter from ai-team.repo.json in the given repo.

    Args:
        repo_root: Repository root path. Defaults to current directory.

    Returns:
        Configured adapter, or None if adapter is "none".

    Raises:
        FileNotFoundError: If ai-team.repo.json not found.
        ValueError: If adapter is unknown.
    """
    repo_root = Path(repo_root) if repo_root else Path.cwd()
    profile_path = repo_root / "ai-team.repo.json"

    if not profile_path.exists():
        raise FileNotFoundError(f"Profile not found: {profile_path}")

    profile = json.loads(profile_path.read_text())
    work_item_source = profile.get("work_item_source", {})
    adapter_name = work_item_source.get("adapter", "none")

    if adapter_name == "none":
        return None

    # Get the provider-specific config (e.g., work_item_source.notion)
    provider_config = work_item_source.get(adapter_name, {})

    return get_adapter(adapter_name, provider_config)


def _ensure_adapters_loaded():
    """Import adapter modules to trigger registration."""
    if not _ADAPTERS:
        # Import adapters to register them via @register_adapter
        # Let ImportError propagate — indicates broken install, not optional dep
        from mat_runtime.work_items import notion  # noqa: F401
        from mat_runtime.work_items import github_issues  # noqa: F401
        # Future: linear, jira
