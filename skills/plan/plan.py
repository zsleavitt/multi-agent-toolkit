#!/usr/bin/env python3
"""
/plan skill — plan and decompose tasks without executing.

Usage:
    python plan.py <goal> [--scope-paths <paths>] [--timeout-ms <ms>]

Invokes the orchestrator agent for planning only — no code changes are made.
"""

from __future__ import annotations

import argparse
import sys
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from mat_runtime.router import AgentRouter, MAT2Request
from skills.lib.formatting import format_error, format_success


def main() -> int:
    parser = argparse.ArgumentParser(description="Plan and decompose tasks (no execution)")
    parser.add_argument("goal", nargs="+", help="Goal or task to plan")
    parser.add_argument("--scope-paths", "-s", nargs="*", help="Paths to scope the planning to")
    parser.add_argument("--timeout-ms", "-t", type=int, default=300000, help="Timeout in ms (default: 5 min)")
    parser.add_argument("--repo-root", "-r", type=Path, default=Path.cwd(), help="Repository root")
    parser.add_argument("--json", "-j", action="store_true", help="Output raw JSON")

    args = parser.parse_args()
    goal = " ".join(args.goal)

    # Prepend planning instruction to ensure no execution
    planning_instruction = (
        f"Create a detailed plan for the following goal. "
        f"Do NOT execute or implement anything — only produce a plan with work items, "
        f"dependencies, and routing recommendations.\n\nGoal: {goal}"
    )

    request = MAT2Request(
        schema_version="1.2.0",
        correlation_id=str(uuid.uuid4()),
        idempotency_key=str(uuid.uuid4()),
        op="codex.diagnose",  # Diagnose is read-only analysis, appropriate for planning
        repo_root=str(args.repo_root.absolute()),
        instruction=planning_instruction,
        scope_paths=args.scope_paths or [],
        timeout_ms=args.timeout_ms,
    )

    try:
        router = AgentRouter(repo_root=args.repo_root)
    except Exception as e:
        print(f"Error initializing router: {e}", file=sys.stderr)
        return 1

    response = router.invoke("orchestrator", request)

    if args.json:
        print(response.to_json(indent=2))
    elif response.ok:
        print(format_success(response, "Plan"))
    else:
        print(format_error(response, "orchestrator"), file=sys.stderr)

    return 0 if response.ok else 1


if __name__ == "__main__":
    sys.exit(main())
