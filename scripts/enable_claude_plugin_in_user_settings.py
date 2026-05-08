#!/usr/bin/env python3
"""Optional: force ``multi-agent-toolkit@mat-toolkit`` on in Claude user ``settings.json``.

``claude plugin install`` normally sets ``enabledPlugins``. Use this only if you
need to toggle the plugin on by hand. Prefer ``scripts/register_mat_claude_plugin.py``.

Stale keys like ``multi-agent-toolkit@local`` are unreliable: Claude treats the
suffix as a *marketplace id*, not \"install from disk\".
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_PLUGIN_ENABLE_KEY = "multi-agent-toolkit@mat-toolkit"


def merge(settings_path: Path) -> None:
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
    merged[_PLUGIN_ENABLE_KEY] = True
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
    args = p.parse_args()

    home = Path.home()
    settings_path = (
        args.settings_json.expanduser().resolve()
        if args.settings_json is not None
        else (home / ".claude" / "settings.json")
    )
    merge(settings_path)
    print(f"set {_PLUGIN_ENABLE_KEY!r} true in {settings_path}")


if __name__ == "__main__":
    main()
