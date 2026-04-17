#!/usr/bin/env python3
"""
/diagnose skill — debug and investigate issues.

Usage:
    python diagnose.py <issue> [--scope-paths <paths>] [--timeout-ms <ms>]

Invokes the coder agent with codex.diagnose for root cause analysis.
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
    parser = argparse.ArgumentParser(description="Debug and investigate issues")
    parser.add_argument("issue", nargs="+", help="Issue description to diagnose")
    parser.add_argument("--scope-paths", "-s", nargs="*", help="Paths to scope the diagnosis to")
    parser.add_argument("--timeout-ms", "-t", type=int, default=300000, help="Timeout in ms (default: 5 min)")
    parser.add_argument("--repo-root", "-r", type=Path, default=Path.cwd(), help="Repository root")
    parser.add_argument("--json", "-j", action="store_true", help="Output raw JSON")

    args = parser.parse_args()
    issue = " ".join(args.issue)

    request = MAT2Request(
        schema_version="1.2.0",
        correlation_id=str(uuid.uuid4()),
        idempotency_key=str(uuid.uuid4()),
        op="codex.diagnose",
        repo_root=str(args.repo_root.absolute()),
        instruction=issue,
        scope_paths=args.scope_paths or [],
        timeout_ms=args.timeout_ms,
    )

    try:
        router = AgentRouter(repo_root=args.repo_root)
    except Exception as e:
        print(f"Error initializing router: {e}", file=sys.stderr)
        return 1

    response = router.invoke("coder", request)

    if args.json:
        print(response.to_json(indent=2))
    elif response.ok:
        print(format_success(response, "Diagnosis"))
    else:
        print(format_error(response, "coder"), file=sys.stderr)

    return 0 if response.ok else 1


if __name__ == "__main__":
    sys.exit(main())
