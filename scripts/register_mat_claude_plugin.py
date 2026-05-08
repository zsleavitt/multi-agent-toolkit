#!/usr/bin/env python3
"""Register this repo as a Claude Code marketplace and install the bundled plugin.

Claude Code resolves plugins as name@marketplace (see Discover and install plugins:
https://code.claude.com/docs/en/discover-plugins ). The id multi-agent-toolkit@local
is wrong here: "local" is treated as a marketplace name, not "install from disk".

This repository ships .claude-plugin/marketplace.json (id mat-toolkit). Setup runs:

  claude plugin marketplace add <repo-root> --scope user
  claude plugin install multi-agent-toolkit@mat-toolkit --scope user
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

_MARKETPLACE = "mat-toolkit"
_PLUGIN = f"multi-agent-toolkit@{_MARKETPLACE}"


def _run(claude: str, args: list[str]) -> int:
    return subprocess.call([claude, *args])


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--repo-root",
        type=Path,
        required=True,
        help="Absolute path to this repository (directory containing .claude-plugin/marketplace.json)",
    )
    args = p.parse_args()
    repo = args.repo_root.expanduser().resolve()
    mp = repo / ".claude-plugin" / "marketplace.json"
    if not mp.is_file():
        print(f"error: missing {mp}", file=sys.stderr)
        return 1

    claude = shutil.which("claude")
    if not claude:
        print(
            "warning: `claude` not on PATH; skipped Claude plugin registration. "
            f"Add the marketplace and install when ready:\n"
            f"  claude plugin marketplace add {repo}\n"
            f"  claude plugin install {_PLUGIN}",
            file=sys.stderr,
        )
        return 0

    repo_s = str(repo)
    exit_m = _run(claude, ["plugin", "marketplace", "add", repo_s, "--scope", "user"])
    if exit_m != 0:
        return exit_m
    exit_i = _run(claude, ["plugin", "install", _PLUGIN, "--scope", "user"])
    if exit_i != 0:
        return exit_i
    print(f"Claude Code: marketplace {_MARKETPLACE!r} + plugin {_PLUGIN!r} (user scope)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
