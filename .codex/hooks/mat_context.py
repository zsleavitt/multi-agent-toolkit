#!/usr/bin/env python3
"""
MAT context hooks for Codex (SessionStart, UserPromptSubmit).

Contracts follow Codex command hooks:
https://developers.openai.com/codex/hooks

stdin:  one JSON object per run (see .codex/README.md).
stdout: one JSON object; exit code 0 on success (Codex continues).
stderr: unused on success; avoid logging full user prompts (PII).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


def get_repo_root() -> Path:
    """Repository root (parent of `.codex/`)."""
    return Path(__file__).resolve().parent.parent.parent


def build_session_context(repo_root: Path) -> str:
    """SessionStart: MAT-1 vs MAT-2 and pointers to contracts."""
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


def build_user_prompt_context(repo_root: Path) -> str:
    """UserPromptSubmit: short guardrails (no large file dumps)."""
    return f"""### MAT quick reminders (UserPromptSubmit)

- You are a **MAT-2** worker here: code changes and verification, not direct git push/branch operations.
- Prefer existing workflows under `lib/skills/` (e.g. `lib/skills/develop/`, `lib/skills/test/`) instead of inventing new patterns.
- For orchestration and git ops boundaries, see `CLAUDE.md` and `AGENTS.md` at repo root: {repo_root}
- Do not paste secrets or production credentials into the session.
"""


def _resolve_event(data: dict[str, Any]) -> str:
    name = data.get("hook_event_name")
    if isinstance(name, str) and name:
        return name
    # Codex supplies hook_event_name; fall back for minimal / manual stdin.
    if "prompt" in data:
        return "UserPromptSubmit"
    return "SessionStart"


def build_response(event: str, repo_root: Path) -> dict[str, Any]:
    if event == "UserPromptSubmit":
        text = build_user_prompt_context(repo_root)
        return {
            "continue": True,
            "hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit",
                "additionalContext": text,
            },
        }

    # SessionStart (default)
    text = build_session_context(repo_root)
    return {
        "continue": True,
        "systemMessage": text,
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": text,
        },
    }


def main() -> int:
    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        data = {}

    if not isinstance(data, dict):
        data = {}

    repo_root = get_repo_root()
    event = _resolve_event(data)
    response = build_response(event, repo_root)

    json.dump(response, sys.stdout)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
