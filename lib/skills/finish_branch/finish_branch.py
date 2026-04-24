#!/usr/bin/env python3
"""
/finish-branch skill — close work items when branch is merged.

Usage:
    python finish_branch.py [--branch BRANCH] [--comment COMMENT] [--repo-root PATH]

If --branch is not provided, uses current git branch.

This script:
1. Extracts work item reference from branch name (e.g., MAT-42)
2. Reads adapter config from ai-team.repo.json
3. Closes/transitions the work item via appropriate adapter
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

# Add repo root to path for imports
REPO_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from lib.skills.finish_branch.adapter_factory import get_close_adapter
from lib.skills.finish_branch.branch_parser import extract_work_item_ref


def get_current_branch() -> str | None:
    """Get current git branch name."""
    try:
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None


def is_branch_merged(branch: str, base_branch: str = "main") -> bool:
    """
    Check if a branch has been merged into the base branch.

    Args:
        branch: Branch name to check.
        base_branch: Base branch to check against (default: main).

    Returns:
        True if branch is merged, False otherwise.
    """
    try:
        # Check if branch is in the list of merged branches
        result = subprocess.run(
            ["git", "branch", "--merged", base_branch],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
        merged_branches = [b.strip().lstrip("* ") for b in result.stdout.splitlines()]
        return branch in merged_branches
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return False


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Close work items when branch is merged"
    )
    parser.add_argument(
        "--branch",
        "-b",
        help="Branch name to extract work item from (default: current branch)",
    )
    parser.add_argument(
        "--comment",
        "-c",
        help="Comment to add when closing",
    )
    parser.add_argument(
        "--repo-root",
        "-r",
        type=Path,
        default=Path.cwd(),
        help="Repository root (default: current directory)",
    )
    parser.add_argument(
        "--dry-run",
        "-n",
        action="store_true",
        help="Show what would be done without actually closing",
    )
    parser.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="Close work item even if branch is not merged",
    )
    parser.add_argument(
        "--base-branch",
        default="main",
        help="Base branch to check merge status against (default: main)",
    )

    args = parser.parse_args()

    # Get branch name
    branch = args.branch or get_current_branch()
    if not branch:
        result = {
            "ok": False,
            "error": "Could not determine branch name. Use --branch to specify.",
        }
        print(json.dumps(result, indent=2))
        return 1

    # Extract work item reference
    work_item_ref = extract_work_item_ref(branch)
    if not work_item_ref:
        result = {
            "ok": True,
            "message": f"No work item reference found in branch '{branch}'. Nothing to close.",
            "branch": branch,
        }
        print(json.dumps(result, indent=2))
        return 0

    # Get adapter
    try:
        adapter = get_close_adapter(args.repo_root)
    except FileNotFoundError as e:
        result = {
            "ok": False,
            "error": str(e),
            "suggestion": "Create ai-team.repo.json or run setup wizard.",
        }
        print(json.dumps(result, indent=2))
        return 1
    except ValueError as e:
        result = {
            "ok": False,
            "error": str(e),
        }
        print(json.dumps(result, indent=2))
        return 1

    # Check if branch is merged (unless --force is used)
    if not args.force and not is_branch_merged(branch, args.base_branch):
        result = {
            "ok": False,
            "error": f"Branch '{branch}' is not merged into '{args.base_branch}'. "
                     f"Use --force to close anyway, or merge the branch first.",
            "branch": branch,
            "work_item_ref": work_item_ref,
            "base_branch": args.base_branch,
        }
        print(json.dumps(result, indent=2))
        return 1

    # Dry run mode
    if args.dry_run:
        result = {
            "ok": True,
            "dry_run": True,
            "message": f"Would close {work_item_ref} using {adapter.adapter_name} adapter",
            "branch": branch,
            "work_item_ref": work_item_ref,
            "adapter": adapter.adapter_name,
        }
        print(json.dumps(result, indent=2))
        return 0

    # Close the work item
    close_result = adapter.close(work_item_ref, comment=args.comment)

    result = {
        "ok": close_result.ok,
        "branch": branch,
        "work_item_ref": work_item_ref,
        "adapter": adapter.adapter_name,
        "message": close_result.message,
    }

    if close_result.item_id:
        result["item_id"] = close_result.item_id
    if close_result.item_url:
        result["item_url"] = close_result.item_url
    if close_result.error:
        result["error"] = close_result.error

    print(json.dumps(result, indent=2))
    return 0 if close_result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
