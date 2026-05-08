#!/usr/bin/env python3
"""Print Codex user-config next steps and optionally enable codex_hooks idempotently.

Reads the repo's ``.codex/config.toml.example`` for the canonical snippet. User
config lives at:

  macOS / Linux: ~/.codex/config.toml
  Windows:       %USERPROFILE%\\.codex\\config.toml  (Path.home() / ".codex")
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

_CODEX_HOOKS_TRUE = re.compile(r"(?m)^\s*codex_hooks\s*=\s*true\b")
_CODEX_HOOKS_FALSE = re.compile(r"(?m)^\s*codex_hooks\s*=\s*false\b")
_FEATURES_HEADER = re.compile(r"^\s*\[features\]\s*$")


def user_codex_config_path() -> Path:
    return Path.home() / ".codex" / "config.toml"


def load_snippet(repo_root: Path) -> str:
    example = repo_root / ".codex" / "config.toml.example"
    if not example.is_file():
        return "[features]\ncodex_hooks = true\n"
    text = example.read_text(encoding="utf-8")
    lines: list[str] = []
    capture = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("[features]"):
            capture = True
            lines.append("[features]")
            continue
        if capture:
            if stripped.startswith("#") and "codex_hooks" in stripped:
                continue
            if stripped.startswith("codex_hooks"):
                lines.append("codex_hooks = true")
                break
            if stripped.startswith("[") and stripped.endswith("]"):
                break
    if not lines:
        return "[features]\ncodex_hooks = true\n"
    result = "\n".join(lines) + "\n"
    if "codex_hooks" not in result:
        return "[features]\ncodex_hooks = true\n"
    return result


def merge_codex_hooks_into_existing(text: str) -> str | None:
    """Return new file body with ``codex_hooks = true`` inserted, or None if no change."""
    if _CODEX_HOOKS_TRUE.search(text):
        return None
    if _CODEX_HOOKS_FALSE.search(text):
        return None

    parts = text.splitlines(keepends=True)
    if not parts:
        return "[features]\ncodex_hooks = true\n"

    idx: int | None = None
    for i, line in enumerate(parts):
        if _FEATURES_HEADER.match(line.rstrip("\r\n")):
            idx = i
            break

    if idx is None:
        out = text
        if out and not out.endswith("\n"):
            out += "\n"
        return out + "\n# Added by multi-agent-toolkit setup (idempotent)\n[features]\ncodex_hooks = true\n"

    insert_at = idx + 1
    while insert_at < len(parts):
        cur = parts[insert_at]
        stripped = cur.lstrip()
        if stripped.startswith("["):
            break
        if re.match(r"^\s*codex_hooks\s*=", cur):
            return None
        insert_at += 1
    parts.insert(insert_at, "codex_hooks = true\n")
    return "".join(parts)


def apply_user_config(user_path: Path, snippet: str) -> str:
    """Create or update user config. Returns a short status label."""
    user_path.parent.mkdir(parents=True, exist_ok=True)
    if not user_path.is_file():
        user_path.write_text(snippet, encoding="utf-8")
        return "created"

    body = user_path.read_text(encoding="utf-8")
    if _CODEX_HOOKS_TRUE.search(body):
        return "already_enabled"

    if _CODEX_HOOKS_FALSE.search(body):
        return "skipped_explicit_false"

    merged = merge_codex_hooks_into_existing(body)
    if merged is None:
        return "already_enabled"
    user_path.write_text(merged, encoding="utf-8")
    return "merged"


def print_instructions(repo_root: Path, user_path: Path) -> None:
    print("")
    print("Codex — enable project hooks under .codex/")
    print("-------------------------------------------")
    print(f"  User config file:  {user_path}")
    print(f"  Project hooks dir:  {repo_root / '.codex'}")
    print("")
    print("  1) [features] codex_hooks = true")
    print("     Merge the snippet from .codex/config.toml.example into the user")
    print("     file above (Unix: ~/.codex/config.toml, Windows: %USERPROFILE%\\.codex\\config.toml).")
    print("")
    print("  2) codex auth")
    print("     Authenticate the Codex CLI with OpenAI if you have not already.")
    print("")
    print("  3) Trust this repository in Codex when prompted so project-local")
    print("     .codex/hooks.json is loaded (trust model: see .codex/README.md).")
    print("")
    print("  Docs: .codex/README.md — optional guardrails: .codex/guardrails.toml.example")
    print("")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo-root", type=Path, required=True)
    p.add_argument(
        "--apply",
        action="store_true",
        help="Idempotently create or merge codex_hooks=true into user config.toml",
    )
    args = p.parse_args()
    repo = args.repo_root.expanduser().resolve()
    user_path = user_codex_config_path()
    snippet = load_snippet(repo)

    print_instructions(repo, user_path)

    if args.apply:
        try:
            status = apply_user_config(user_path, snippet)
        except OSError as e:
            print(f"error: could not write {user_path}: {e}", file=sys.stderr)
            return 1
        labels = {
            "created": f"Wrote {user_path} with codex_hooks = true.",
            "merged": f"Updated {user_path}: inserted codex_hooks = true under [features] or appended [features].",
            "already_enabled": f"{user_path} already enables codex_hooks (no change).",
            "skipped_explicit_false": f"{user_path} sets codex_hooks = false; left unchanged.",
        }
        print(labels.get(status, status))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
