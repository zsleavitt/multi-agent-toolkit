#!/usr/bin/env python3
"""
/review-pr skill — code review via reviewer agent.

Usage:
    python review_pr.py <target> [--scope-paths <paths>] [--timeout-ms <ms>]

Invokes the reviewer agent directly for focused code review.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from mat_runtime.router import AgentRouter, MAT2Request
from lib.skills.formatting import format_error, format_success
from lib.skills.github_review import (
    check_gh_cli,
    detect_pr_for_branch,
    filter_findings_by_severity,
    build_review_payload,
    post_review,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Code review via reviewer agent")
    parser.add_argument("target", nargs="+", help="What to review (file, PR, description)")
    parser.add_argument("--scope-paths", "-s", nargs="*", help="Paths to scope the review to")
    parser.add_argument("--timeout-ms", "-t", type=int, default=300000, help="Timeout in ms (default: 5 min)")
    parser.add_argument("--repo-root", "-r", type=Path, default=Path.cwd(), help="Repository root")
    parser.add_argument("--json", "-j", action="store_true", help="Output raw JSON")
    parser.add_argument("--post", "-p", action="store_true", help="Post findings as GitHub PR review")
    parser.add_argument(
        "--min-severity",
        "-m",
        choices=["info", "suggestion", "issue", "blocker"],
        default="info",
        help="Minimum severity to post (default: info)",
    )

    args = parser.parse_args()
    target = " ".join(args.target)

    request = MAT2Request(
        schema_version="1.2.0",
        correlation_id=str(uuid.uuid4()),
        idempotency_key=str(uuid.uuid4()),
        op="codex.review",
        repo_root=str(args.repo_root.absolute()),
        instruction=target,
        scope_paths=args.scope_paths or [],
        timeout_ms=args.timeout_ms,
    )

    try:
        router = AgentRouter(repo_root=args.repo_root)
    except Exception as e:
        print(f"Error initializing router: {e}", file=sys.stderr)
        return 1

    response = router.invoke("reviewer", request)

    # Handle --post flag for GitHub PR comments
    posted_pr = None
    if args.post and response.ok:
        # Check gh CLI availability
        gh_ok, gh_error = check_gh_cli()
        if not gh_ok:
            print(f"Error: {gh_error}", file=sys.stderr)
            print("\nFalling back to CLI output only.\n", file=sys.stderr)
        else:
            # Detect PR for current branch
            pr_info = detect_pr_for_branch()
            if pr_info is None:
                # Prompt to create PR
                create = input("No PR found for current branch. Create one? [y/N] ").strip().lower()
                if create == "y":
                    result = subprocess.run(["gh", "pr", "create"], check=False)
                    if result.returncode == 0:
                        pr_info = detect_pr_for_branch()

            if pr_info:
                # Get findings from response
                findings = response.result.get("findings", [])
                filtered = filter_findings_by_severity(findings, args.min_severity)

                if filtered:
                    payload = build_review_payload(filtered)
                    post_ok, post_error = post_review(pr_info, payload)
                    if post_ok:
                        posted_pr = pr_info["number"]
                    else:
                        print(f"Error posting review: {post_error}", file=sys.stderr)
                        print("\nFalling back to CLI output only.\n", file=sys.stderr)
                else:
                    print("No findings meet minimum severity threshold.", file=sys.stderr)
            else:
                print("\nNo PR available. Showing CLI output only.\n", file=sys.stderr)

    if args.json:
        print(response.to_json(indent=2))
    elif response.ok:
        print(format_success(response, "Code Review"))
    else:
        print(format_error(response, "reviewer"), file=sys.stderr)

    if posted_pr:
        print(f"\n✓ Posted review to PR #{posted_pr}")

    return 0 if response.ok else 1


if __name__ == "__main__":
    sys.exit(main())
