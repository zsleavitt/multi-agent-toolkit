#!/usr/bin/env python3
"""Merge multi-agent-toolkit@local into Claude Code installed_plugins.json."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _norm(p: str) -> str:
    try:
        return str(Path(p).resolve()).lower()
    except OSError:
        return str(p).lower()


def merge(path: Path, repo_root: Path, *, plugin_key: str = "multi-agent-toolkit@local") -> None:
    repo = repo_root.resolve()
    target = _norm(str(repo))

    data: dict = {}
    if path.exists() and path.stat().st_size > 0:
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                data = loaded
        except json.JSONDecodeError:
            data = {}

    now = _utc_stamp()
    prior_installed: str | None = None
    existing = data.get(plugin_key)
    if isinstance(existing, list):
        for entry in existing:
            if _norm(str(entry.get("installPath", ""))) == target:
                prior_installed = entry.get("installedAt")
                break

    entry = {
        "scope": "user",
        "installPath": str(repo),
        "version": "1.0.0",
        "installedAt": prior_installed or now,
        "lastUpdated": now,
    }

    if existing is None:
        data[plugin_key] = [entry]
    elif isinstance(existing, list):
        kept = [e for e in existing if _norm(str(e.get("installPath", ""))) != target]
        kept.append(entry)
        data[plugin_key] = kept
    else:
        data[plugin_key] = [existing, entry]

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--plugins-json", type=Path, required=True, help="Path to installed_plugins.json")
    p.add_argument("--repo-root", type=Path, required=True, help="Absolute path to multi-agent-toolkit checkout")
    args = p.parse_args()
    merge(args.plugins_json, args.repo_root)


if __name__ == "__main__":
    main()
