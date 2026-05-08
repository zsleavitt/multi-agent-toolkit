#!/usr/bin/env python3
"""Enable multi-agent-toolkit in Claude Code user ``settings.json``.

Claude Code tracks installs in ``~/.claude/plugins/installed_plugins.json`` but only
loads plugins that are also toggled on under ``enabledPlugins`` in
``~/.claude/settings.json`` (user scope). Without this merge, skills stay invisible.

This script sets ``enabledPlugins`` keys that match common local-install conventions:

- ``multi-agent-toolkit@local`` (pairs with ``merge_installed_plugins_json.py``)
- ``multi-agent-toolkit@<absolute-repo-path>`` (some Claude Code builds / CLI flows)

Other keys in ``enabledPlugins`` are preserved.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_DEFAULT_INSTALL_KEY = "multi-agent-toolkit@local"


def _enable_keys(repo_root: Path) -> list[str]:
    repo = repo_root.resolve()
    path_key = f"multi-agent-toolkit@{repo.as_posix()}"
    keys = [_DEFAULT_INSTALL_KEY, path_key]
    # Windows: enabledPlugins keys sometimes mirror the native installPath string.
    native = str(repo)
    if native != repo.as_posix():
        keys.append(f"multi-agent-toolkit@{native}")
    # Deduplicate while preserving order
    seen: set[str] = set()
    out: list[str] = []
    for k in keys:
        if k not in seen:
            seen.add(k)
            out.append(k)
    return out


def merge(settings_path: Path, repo_root: Path) -> None:
    repo_root = repo_root.resolve()
    keys = _enable_keys(repo_root)

    data: dict = {}
    if settings_path.exists() and settings_path.stat().st_size > 0:
        raw = settings_path.read_text(encoding="utf-8")
        try:
            loaded = json.loads(raw)
            if isinstance(loaded, dict):
                data = loaded
        except json.JSONDecodeError as e:
            print(
                f"error: {settings_path}: invalid JSON ({e}). "
                "Fix the file or merge enabledPlugins manually.",
                file=sys.stderr,
            )
            raise SystemExit(1) from e

    existing = data.get("enabledPlugins")
    merged: dict[str, bool] = {}
    if isinstance(existing, dict):
        for k, v in existing.items():
            if isinstance(k, str):
                merged[k] = bool(v)
    for k in keys:
        merged[k] = True
    data["enabledPlugins"] = merged

    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--settings-json",
        type=Path,
        default=None,
        help="Path to Claude user settings.json (default: ~/.claude/settings.json)",
    )
    p.add_argument(
        "--repo-root",
        type=Path,
        required=True,
        help="Absolute path to multi-agent-toolkit checkout",
    )
    args = p.parse_args()

    home = Path.home()
    settings_path = (
        args.settings_json.expanduser().resolve()
        if args.settings_json is not None
        else (home / ".claude" / "settings.json")
    )
    merge(settings_path, args.repo_root.expanduser().resolve())
    print(f"wrote enabledPlugins for multi-agent-toolkit in {settings_path}")


if __name__ == "__main__":
    main()
