#!/usr/bin/env python3
"""
/review-pr skill — code review via reviewer agent.

Usage:
    python3 lib/skills/review-pr/review_pr.py <target> [--scope-paths <paths>] [--timeout-ms <ms>]

(With a project venv: `source .venv/bin/activate` then `python` resolves to the same interpreter.)

Invokes the reviewer agent directly for focused code review.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

# https://github.com/owner/repo/pull/123
_GH_PR_URL = re.compile(
    r"https?://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+)/pull/(?P<num>\d+)",
    re.IGNORECASE,
)


def enrich_instruction_for_github_pr(
    target: str,
    repo_root: Path,
) -> str:
    """
    If `target` is a GitHub PR URL, resolve base branch via `gh` and prefix the instruction.
    """
    m = _GH_PR_URL.search(target.strip())
    if not m:
        return target
    owner = m.group("owner")
    repo = m.group("repo")
    num = m.group("num")
    try:
        r = subprocess.run(
            [
                "gh",
                "pr",
                "view",
                num,
                "-R",
                f"{owner}/{repo}",
                "--json",
                "baseRefName",
            ],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=repo_root,
            stdin=subprocess.DEVNULL,
        )
        if r.returncode != 0:
            gh_err = (r.stderr or r.stdout or "error").strip()
            return (
                f"Review GitHub PR #{num} in {owner}/{repo} (merge base: unknown, gh failed: {gh_err!r}).\n"
                f"{target}"
            )
        data = json.loads(r.stdout)
        base = data.get("baseRefName", "unknown")
    except (OSError, json.JSONDecodeError, subprocess.TimeoutExpired) as e:
        return f"Review GitHub PR #{num} in {owner}/{repo} (merge base: unknown, {e}).\n{target}"
    return f"Review PR #{num} in {owner}/{repo} (merge base: {base}).\n{target}"

from mat_runtime.router import AgentRouter, MAT2Request
from mat_runtime.swarm import Swarm, SwarmTask
from mat_runtime.adapters import get_adapter
from lib.skills.formatting import format_error, format_success
from lib.skills.github_review import (
    check_gh_cli,
    detect_pr_for_branch,
    filter_findings_by_severity,
    build_review_payload,
    post_review,
)


def try_post_review(response, min_severity: str) -> int | None:
    """
    Attempt to post review findings to GitHub PR.

    Args:
        response: MAT2Response from reviewer agent.
        min_severity: Minimum severity level to post.

    Returns:
        PR number if posted successfully, None otherwise.
    """
    # Check gh CLI availability
    gh_ok, gh_error = check_gh_cli()
    if not gh_ok:
        print(f"Error: {gh_error}", file=sys.stderr)
        print("\nFalling back to CLI output only.\n", file=sys.stderr)
        return None

    # Detect PR for current branch
    pr_info = detect_pr_for_branch()
    if pr_info is None:
        # Prompt to create PR (only in interactive mode)
        if sys.stdin.isatty():
            create = input("No PR found for current branch. Create one? [y/N] ").strip().lower()
            if create == "y":
                result = subprocess.run(["gh", "pr", "create"], check=False)
                if result.returncode == 0:
                    pr_info = detect_pr_for_branch()
        else:
            print("No PR found for current branch. Skipping GitHub posting.", file=sys.stderr)

    if not pr_info:
        print("\nNo PR available. Showing CLI output only.\n", file=sys.stderr)
        return None

    # Get findings from response
    findings = response.result.get("findings", [])
    filtered = filter_findings_by_severity(findings, min_severity)

    if not filtered:
        print("No findings meet minimum severity threshold.", file=sys.stderr)
        return None

    payload = build_review_payload(filtered)
    post_ok, post_error = post_review(pr_info, payload)
    if post_ok:
        return pr_info["number"]
    else:
        print(f"Error posting review: {post_error}", file=sys.stderr)
        print("\nFalling back to CLI output only.\n", file=sys.stderr)
        return None


MAX_DIFF_CHARS = 50000


def prefetch_pr_for_swarm(
    target: str,
    repo_root: Path,
) -> dict | None:
    """
    Pre-fetch PR metadata and diff for swarm review.

    Returns dict with pr_url, title, base_ref, head_ref, diff, or None if not a PR URL.
    """
    m = _GH_PR_URL.search(target.strip())
    if not m:
        return None

    owner = m.group("owner")
    repo = m.group("repo")
    num = m.group("num")
    pr_url = f"https://github.com/{owner}/{repo}/pull/{num}"

    # Fetch PR metadata
    try:
        meta_result = subprocess.run(
            [
                "gh", "pr", "view", num,
                "-R", f"{owner}/{repo}",
                "--json", "title,baseRefName,headRefName",
            ],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=repo_root,
            stdin=subprocess.DEVNULL,
        )
        if meta_result.returncode != 0:
            print(f"Warning: gh pr view failed: {meta_result.stderr}", file=sys.stderr)
            return None
        meta = json.loads(meta_result.stdout)
    except (OSError, json.JSONDecodeError, subprocess.TimeoutExpired) as e:
        print(f"Warning: Failed to fetch PR metadata: {e}", file=sys.stderr)
        return None

    # Fetch PR diff
    try:
        diff_result = subprocess.run(
            ["gh", "pr", "diff", num, "-R", f"{owner}/{repo}"],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=repo_root,
            stdin=subprocess.DEVNULL,
        )
        if diff_result.returncode != 0:
            print(f"Warning: gh pr diff failed: {diff_result.stderr}", file=sys.stderr)
            return None
        diff_content = diff_result.stdout
    except (OSError, subprocess.TimeoutExpired) as e:
        print(f"Warning: Failed to fetch PR diff: {e}", file=sys.stderr)
        return None

    return {
        "pr_url": pr_url,
        "title": meta.get("title", "(no title)"),
        "base_ref": meta.get("baseRefName", "unknown"),
        "head_ref": meta.get("headRefName", "unknown"),
        "diff": diff_content,
    }


def build_swarm_review_prompt(pr_data: dict) -> str:
    """
    Build a structured review prompt from pre-fetched PR data.

    Includes metadata and diff, with truncation for large diffs.
    """
    diff_content = pr_data["diff"]
    truncated = False

    if len(diff_content) > MAX_DIFF_CHARS:
        diff_content = diff_content[:MAX_DIFF_CHARS]
        truncated = True

    prompt = f"""Review the following pull request changes and return severity-ranked findings.

PR: {pr_data['pr_url']}
Title: {pr_data['title']}
Base branch: {pr_data['base_ref']} → {pr_data['head_ref']}

Format each finding as:
[SEVERITY] Brief title
File: path/to/file.py:line_number
Description of the issue and why it matters.

Severity levels: blocker, issue, suggestion, info

--- DIFF ---
{diff_content}"""

    if truncated:
        prompt += "\n\n[diff truncated at 50k chars — focus on the changes shown above]"

    return prompt


def _build_consolidation_prompt(swarm_result) -> str:
    """Build the prompt for Claude to consolidate multi-model review outputs."""
    parts = []
    parts.append("""You are consolidating code review findings from multiple AI reviewers.
Below are independent reviews of the same PR from Claude, Codex, and Gemini.

Synthesize them into a single unified review:
- Merge duplicate findings (same issue spotted by multiple reviewers = one finding, note agreement)
- Preserve unique findings from each reviewer
- Rank by severity: blocker > issue > suggestion > info
- Keep the same output format: [SEVERITY] Title / File:line / Description
""")

    for candidate in ["claude", "codex-review", "gemini"]:
        label = candidate.upper().replace("-", " ")
        candidate_data = swarm_result.output.get(candidate, {})
        if candidate_data.get("ok"):
            output = candidate_data.get("output", "(no output)")
        else:
            error = candidate_data.get("error", "unknown error")
            output = f"Review failed — {error}"
        parts.append(f"\n--- {label} ---\n{output}")

    return "\n".join(parts)


def run_swarm_review(
    instruction: str,
    repo_root: Path,
    timeout_ms: int,
    original_target: str,
) -> tuple[bool, str, list[str], dict | None]:
    """
    Run multi-model review using the swarm and consolidate results.

    For GitHub PR URLs, pre-fetches the diff to normalize input for all models.
    Returns (ok, output, successful_models, pr_data) tuple.
    """
    swarm_path = REPO_ROOT / "swarms" / "multi-model-review.json"
    if not swarm_path.exists():
        return False, f"Swarm definition not found: {swarm_path}", [], None

    try:
        swarm = Swarm(definition_path=swarm_path, repo_root=repo_root)
    except Exception as e:
        return False, f"Failed to initialize swarm: {e}", [], None

    # Pre-fetch PR data if target is a GitHub PR URL
    pr_data = prefetch_pr_for_swarm(original_target, repo_root)
    if pr_data:
        # Use structured prompt with pre-fetched diff
        swarm_instruction = build_swarm_review_prompt(pr_data)
        print(f"Pre-fetched PR #{pr_data['pr_url'].split('/')[-1]}: {pr_data['title']}", file=sys.stderr)
        print(f"Diff size: {len(pr_data['diff']):,} chars", file=sys.stderr)
    else:
        # Fall back to original instruction for non-PR targets
        swarm_instruction = instruction

    task = SwarmTask(
        instruction=swarm_instruction,
        op="codex.review",
        correlation_id=str(uuid.uuid4()),
        timeout_ms=timeout_ms,
    )

    import asyncio
    swarm_result = asyncio.run(swarm.dispatch(task))

    # Track which models succeeded
    successful_models = [r.candidate for r in swarm_result.candidate_results if r.ok]

    if not swarm_result.ok:
        error_msg = swarm_result.error.get("message", "All reviewers failed") if swarm_result.error else "Unknown error"
        return False, f"Swarm review failed: {error_msg}", successful_models, pr_data

    # Consolidate with Claude
    consolidation_prompt = _build_consolidation_prompt(swarm_result)
    claude_adapter = get_adapter("claude")
    consolidation_result = claude_adapter.invoke(
        prompt=consolidation_prompt,
        timeout_ms=60000,
    )

    if not consolidation_result.ok:
        # Fall back to raw outputs if consolidation fails
        raw_output = "## Multi-Model Review (consolidation failed)\n\n"
        for candidate, data in swarm_result.output.items():
            raw_output += f"### {candidate.upper()}\n"
            if data.get("ok"):
                raw_output += data.get("output", "(no output)") + "\n\n"
            else:
                raw_output += f"(failed: {data.get('error', 'unknown')})\n\n"
        return True, raw_output, successful_models, pr_data

    return True, consolidation_result.stdout, successful_models, pr_data


def post_swarm_review_to_github(
    pr_url: str,
    consolidated_text: str,
    successful_models: list[str],
) -> tuple[bool, str | None]:
    """
    Post consolidated swarm review as a PR comment.

    Returns (success, error_message) tuple.
    """
    # Extract PR number from URL
    m = _GH_PR_URL.search(pr_url)
    if not m:
        return False, "Could not parse PR URL"

    owner = m.group("owner")
    repo = m.group("repo")
    pr_number = m.group("num")

    # Build reviewer attribution
    model_names = {
        "claude": "Claude",
        "codex-review": "Codex",
        "gemini": "Gemini",
    }
    if successful_models:
        reviewer_list = [model_names.get(m, m) for m in successful_models]
        if len(reviewer_list) == 3:
            reviewer_text = "Claude, Codex, and Gemini"
        else:
            failed = [name for key, name in model_names.items() if key not in successful_models]
            reviewer_text = " and ".join(reviewer_list)
            if failed:
                reviewer_text += f" ({', '.join(failed)} unavailable)"
    else:
        reviewer_text = "multiple models"

    # Build comment body
    comment_body = f"""## Multi-Model Code Review (Claude + Codex + Gemini)

*Reviewed by {reviewer_text} in parallel. Findings consolidated by Claude.*

{consolidated_text}

---
*Generated by [/review-pr --swarm](https://github.com/zsleavitt/multi-agent-toolkit)*"""

    # Post to GitHub
    try:
        result = subprocess.run(
            ["gh", "pr", "comment", pr_number, "-R", f"{owner}/{repo}", "--body", comment_body],
            capture_output=True,
            text=True,
            timeout=60,
            stdin=subprocess.DEVNULL,
        )
        if result.returncode == 0:
            return True, None
        else:
            return False, result.stderr.strip() or "Unknown error"
    except FileNotFoundError:
        return False, "gh CLI not found"
    except subprocess.TimeoutExpired:
        return False, "gh command timed out"
    except Exception as e:
        return False, str(e)


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
    parser.add_argument(
        "--swarm",
        action="store_true",
        help="Use multi-model review (Claude, Codex, Gemini) with consolidation",
    )

    args = parser.parse_args()
    target = " ".join(args.target)
    instruction = enrich_instruction_for_github_pr(target, args.repo_root.resolve())

    # Swarm path: multi-model review with consolidation
    if args.swarm:
        ok, output, successful_models, pr_data = run_swarm_review(
            instruction, args.repo_root, args.timeout_ms, target
        )

        if args.json:
            import json as json_module
            print(json_module.dumps({"ok": ok, "output": output}, indent=2))
            return 0 if ok else 1

        # Always print the review locally
        if ok:
            print("## Multi-Model Code Review (Claude + Codex + Gemini)\n")
            print(output)
        else:
            print(output, file=sys.stderr)
            return 1

        # Post to GitHub if this is a PR URL
        if pr_data and ok:
            post_ok, post_error = post_swarm_review_to_github(
                pr_data["pr_url"], output, successful_models
            )
            if post_ok:
                print(f"\n✓ Review posted to {pr_data['pr_url']}")
            else:
                print(f"\n✗ Could not post to GitHub: {post_error}", file=sys.stderr)

        return 0

    # Single-reviewer path (existing behavior)
    request = MAT2Request(
        schema_version="1.2.0",
        correlation_id=str(uuid.uuid4()),
        idempotency_key=str(uuid.uuid4()),
        op="codex.review",
        repo_root=str(args.repo_root.absolute()),
        instruction=instruction,
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
        posted_pr = try_post_review(response, args.min_severity)

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
