#!/usr/bin/env python3
"""
Skill helper script for invoking MAT agents.

Usage:
    python invoke.py <agent_name> <task_description> [--scope-paths <paths>] [--timeout-ms <ms>]

This script wraps mat_runtime to provide better error handling and output formatting
for use within Claude Code skills.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from pathlib import Path

# Add the repo root to path so we can import mat_runtime
REPO_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from mat_runtime.router import AgentRouter, MAT2Request, MAT2Response


def format_success(response: MAT2Response, agent_name: str) -> str:
    """Format a successful response for display."""
    result = response.result or {}
    output = result.get("output", "")
    files_modified = result.get("files_modified", [])

    lines = [
        f"## Agent: {agent_name}",
        "",
    ]

    if output:
        lines.extend([
            "### Output",
            "",
            output.strip(),
            "",
        ])

    if files_modified:
        lines.extend([
            "### Files Modified",
            "",
        ])
        for f in files_modified:
            lines.append(f"- `{f}`")
        lines.append("")

    return "\n".join(lines)


def format_error(response: MAT2Response, agent_name: str) -> str:
    """Format an error response for display."""
    error = response.error or {}
    code = error.get("code", "unknown")
    message = error.get("message", "An unknown error occurred")

    lines = [
        f"## Agent Error: {agent_name}",
        "",
        f"**Error code:** `{code}`",
        "",
        f"**Message:** {message}",
        "",
    ]

    # Add suggestions based on error code
    if code == "agent_not_found":
        lines.extend([
            "### Suggestions",
            "",
            "- Check the agent name spelling",
            "- Run `python -m mat_runtime list-agents` to see available agents",
            "",
        ])
    elif code == "operation_not_allowed":
        lines.extend([
            "### Suggestions",
            "",
            "- This agent cannot perform the requested operation",
            "- Try a different agent (e.g., `coder` for implementation, `tester` for tests)",
            "",
        ])
    elif code == "timeout":
        lines.extend([
            "### Suggestions",
            "",
            "- The task took too long to complete",
            "- Try breaking it into smaller, more focused tasks",
            "- Increase the timeout with `--timeout-ms`",
            "",
        ])
    elif code == "execution_error":
        lines.extend([
            "### Suggestions",
            "",
            "- Check that the required CLI tool is installed (`bin/setup --check`)",
            "- Verify the CLI tool is authenticated",
            "",
        ])

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Invoke a MAT agent to perform a task"
    )
    parser.add_argument(
        "agent",
        help="Agent name (coder, tester, reviewer, security, researcher, orchestrator)",
    )
    parser.add_argument(
        "task",
        nargs="+",
        help="Task description / instruction",
    )
    parser.add_argument(
        "--scope-paths",
        "-s",
        nargs="*",
        help="Paths to scope the task to",
    )
    parser.add_argument(
        "--timeout-ms",
        "-t",
        type=int,
        default=300000,
        help="Timeout in milliseconds (default: 300000 = 5 minutes)",
    )
    parser.add_argument(
        "--repo-root",
        "-r",
        type=Path,
        default=Path.cwd(),
        help="Repository root (default: current directory)",
    )
    parser.add_argument(
        "--json",
        "-j",
        action="store_true",
        help="Output raw JSON instead of formatted text",
    )
    parser.add_argument(
        "--op",
        "-o",
        default=None,
        help="MAT-2 operation (default: auto-detect based on agent)",
    )

    args = parser.parse_args()

    # Join task words into a single string
    task_description = " ".join(args.task)

    # Auto-detect operation based on agent if not specified
    op = args.op
    if not op:
        op_map = {
            "coder": "codex.implement",
            "tester": "codex.test",
            "reviewer": "codex.review",
            "security": "codex.review",
            "researcher": "codex.diagnose",
            "orchestrator": "codex.diagnose",
        }
        op = op_map.get(args.agent, "codex.implement")

    # Build the request
    request = MAT2Request(
        schema_version="1.2.0",
        correlation_id=str(uuid.uuid4()),
        idempotency_key=str(uuid.uuid4()),
        op=op,
        repo_root=str(args.repo_root.absolute()),
        instruction=task_description,
        scope_paths=args.scope_paths or [],
        timeout_ms=args.timeout_ms,
    )

    # Initialize router and invoke
    try:
        router = AgentRouter(repo_root=args.repo_root)
    except Exception as e:
        print(f"Error initializing router: {e}", file=sys.stderr)
        return 1

    # Check if agent exists
    if not router.find_agent(args.agent):
        available = ", ".join(sorted(router.agents.keys()))
        print(f"Agent '{args.agent}' not found. Available: {available}", file=sys.stderr)
        return 1

    # Invoke the agent
    response = router.invoke(args.agent, request)

    # Output
    if args.json:
        print(response.to_json(indent=2))
    else:
        if response.ok:
            print(format_success(response, args.agent))
        else:
            print(format_error(response, args.agent), file=sys.stderr)

    return 0 if response.ok else 1


if __name__ == "__main__":
    sys.exit(main())
