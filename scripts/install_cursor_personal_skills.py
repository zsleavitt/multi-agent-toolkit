#!/usr/bin/env python3
"""Install multi-agent-toolkit Cursor skills into the user's personal skills directory.

Reads stubs from ``<repo>/.cursor/skills/<skill>/SKILL.md``, rewrites paths to absolute
toolkit locations and prefixes slash commands / skill ``name`` so they work from any
workspace when opened in Cursor.

Default destination: ``~/.cursor/skills`` (``%USERPROFILE%\\.cursor\\skills`` on Windows).

Personal skill folders are named ``multi-agent-toolkit-<skill>`` to avoid collisions.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# Skills shipped under .cursor/skills/ (exclude README-only paths).
_MAT_CURSOR_SKILLS: tuple[str, ...] = (
    "develop",
    "diagnose",
    "plan",
    "review-pr",
    "test",
    "ticket",
)


def _rewrite_skill_md(content: str, repo_root: Path) -> str:
    root = repo_root.resolve()

    for sid in _MAT_CURSOR_SKILLS:
        content = re.sub(
            rf"^name:\s*{re.escape(sid)}\s*$",
            f"name: multi-agent-toolkit-{sid}",
            content,
            flags=re.MULTILINE,
        )

    # Slash-command expansion must not touch `lib/skills/.../develop.py` paths (contains `/develop`).
    tokens: list[tuple[str, str]] = []

    def stash_py(m: re.Match[str]) -> str:
        rel_script = m.group(1)
        script_path = (root / rel_script).resolve()
        token = f"<<<MAT_CURSOR_PY_{len(tokens)}>>>"
        tokens.append((token, f'python "{script_path.as_posix()}"'))
        return token

    content = re.sub(r"python3?\s+(lib/skills/[a-z0-9_./-]+\.py)", stash_py, content)

    def stash_instr(m: re.Match[str]) -> str:
        rel = m.group(1)
        full = (root / rel).resolve().as_posix()
        token = f"<<<MAT_CURSOR_MD_{len(tokens)}>>>"
        tokens.append((token, f"`{full}`"))
        return token

    content = re.sub(r"`(lib/skills/[a-z0-9_./-]+/instructions\.md)`", stash_instr, content)

    # Longest skill ids first so /review-pr wins over accidental shorter matches.
    for sid in sorted(_MAT_CURSOR_SKILLS, key=len, reverse=True):
        content = content.replace(f"/{sid}", f"/multi-agent-toolkit-{sid}")

    for token, replacement in tokens:
        content = content.replace(token, replacement)

    return content


def install(*, repo_root: Path, dest_root: Path, dry_run: bool = False) -> list[Path]:
    """Write transformed SKILL.md files; return paths written."""
    skills_src = repo_root / ".cursor" / "skills"
    written: list[Path] = []
    for sid in _MAT_CURSOR_SKILLS:
        src = skills_src / sid / "SKILL.md"
        if not src.is_file():
            raise FileNotFoundError(f"Missing Cursor skill stub: {src}")
        body = _rewrite_skill_md(src.read_text(encoding="utf-8"), repo_root)
        dest_dir = dest_root / f"multi-agent-toolkit-{sid}"
        dest_file = dest_dir / "SKILL.md"
        if dry_run:
            written.append(dest_file)
            continue
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_file.write_text(body, encoding="utf-8", newline="\n")
        written.append(dest_file)
    return written


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--repo-root",
        type=Path,
        required=True,
        help="Absolute path to multi-agent-toolkit checkout",
    )
    p.add_argument(
        "--dest",
        type=Path,
        default=None,
        help="Personal Cursor skills directory (default: ~/.cursor/skills)",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Print destinations only; do not write files",
    )
    args = p.parse_args()

    repo_root = args.repo_root.expanduser().resolve()
    dest_root = (
        args.dest.expanduser().resolve()
        if args.dest is not None
        else (Path.home() / ".cursor" / "skills")
    )

    if not (repo_root / ".cursor" / "skills").is_dir():
        print(f"error: not a toolkit root (missing .cursor/skills): {repo_root}", file=sys.stderr)
        raise SystemExit(1)

    try:
        paths = install(repo_root=repo_root, dest_root=dest_root, dry_run=args.dry_run)
    except FileNotFoundError as e:
        print(f"error: {e}", file=sys.stderr)
        raise SystemExit(1)

    action = "would write" if args.dry_run else "wrote"
    for path in paths:
        print(f"{action}: {path}")


if __name__ == "__main__":
    main()
