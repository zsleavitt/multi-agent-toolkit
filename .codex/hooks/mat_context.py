#!/usr/bin/env python3
"""
SessionStart hook for Codex — injects MAT context.

Codex Hook Contract:
- stdin: JSON with session_id, cwd, hook_event_name, etc.
- stdout: JSON with continue, systemMessage, hookSpecificOutput, etc.

See: https://developers.openai.com/codex/hooks
"""
import json
import sys
from pathlib import Path


def get_repo_root() -> Path:
    """Return the repository root (where this script lives under .codex/hooks/)."""
    return Path(__file__).resolve().parent.parent.parent


def build_context_message(repo_root: Path) -> str:
    """Build the MAT context message for Codex sessions."""
    return f"""## Multi-Agent Toolkit Context

You are operating in a repository using the Multi-Agent Toolkit (MAT).

### Role Boundaries (IMPORTANT)

- **MAT-1 (Git Ops)**: Branch, fetch, pull, push, staging, commits, diffs — handled by the git executor, NOT Codex.
- **MAT-2 (Code Ops)**: Implement, test, refactor, diagnose, review — this is YOUR role as a Codex worker.

Do NOT attempt git operations directly. The orchestrator (Claude Code) issues MAT-1 requests separately.

### Key Resources

- `CLAUDE.md` — Orchestrator contract and schema overview
- `schemas/` — MAT-1, MAT-2, and other JSON schemas
- `agents/*.md` — Agent role definitions
- `AGENTS.md` — Codex-native agent instructions (if present)

### Schemas

- MAT-1: `schemas/gemini-git-ops/v1/` — Git executor requests/responses
- MAT-2: `schemas/codex-code-exec/v1/` — Your request/response format

Repository root: {repo_root}
"""


def main() -> None:
    """Process SessionStart hook and emit context."""
    try:
        # Read hook input from stdin
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        # If no valid JSON, still emit context (defensive)
        input_data = {}

    repo_root = get_repo_root()
    context_message = build_context_message(repo_root)

    # Emit hook response
    response = {
        "continue": True,
        "systemMessage": context_message,
        "hookSpecificOutput": {
            "additionalContext": context_message
        }
    }

    json.dump(response, sys.stdout)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
