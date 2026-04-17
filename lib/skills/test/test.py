#!/usr/bin/env python3
"""
/test skill — write and run tests via tester agent.

Usage:
    python test.py <task> [--scope-paths <paths>] [--timeout-ms <ms>]

Invokes the tester agent directly for focused testing tasks.
"""

from __future__ import annotations

import argparse
import sys
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from mat_runtime.router import AgentRouter, MAT2Request
from lib.skills.formatting import format_error, format_success


def main() -> int:
    parser = argparse.ArgumentParser(description="Write and run tests via tester agent")
    parser.add_argument("task", nargs="+", help="Testing task description")
    parser.add_argument("--scope-paths", "-s", nargs="*", help="Paths to scope the testing to")
    parser.add_argument("--timeout-ms", "-t", type=int, default=300000, help="Timeout in ms (default: 5 min)")
    parser.add_argument("--repo-root", "-r", type=Path, default=Path.cwd(), help="Repository root")
    parser.add_argument("--json", "-j", action="store_true", help="Output raw JSON")

    args = parser.parse_args()
    task = " ".join(args.task)

    request = MAT2Request(
        schema_version="1.2.0",
        correlation_id=str(uuid.uuid4()),
        idempotency_key=str(uuid.uuid4()),
        op="codex.test",
        repo_root=str(args.repo_root.absolute()),
        instruction=task,
        scope_paths=args.scope_paths or [],
        timeout_ms=args.timeout_ms,
    )

    try:
        router = AgentRouter(repo_root=args.repo_root)
    except Exception as e:
        print(f"Error initializing router: {e}", file=sys.stderr)
        return 1

    response = router.invoke("tester", request)

    if args.json:
        print(response.to_json(indent=2))
    elif response.ok:
        print(format_success(response, "Test Results"))
    else:
        print(format_error(response, "tester"), file=sys.stderr)

    return 0 if response.ok else 1


if __name__ == "__main__":
    sys.exit(main())
