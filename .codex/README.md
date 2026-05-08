# Codex Configuration

This directory contains [Codex](https://openai.com/codex) configuration for the multi-agent-toolkit.

## Prerequisites

1. **Enable hooks** in your user config (`~/.codex/config.toml`):

   See `config.toml.example` in this directory for a copy-paste snippet.

2. **Windows users**: Hooks use `bash -c` for git-root resolution. Install [Git for Windows](https://git-scm.com/download/win) (includes Git Bash) or use WSL.

### User Config

Enable hooks in `~/.codex/config.toml`:

```toml
[features]
codex_hooks = true
```

## Trust Model

Codex loads project-local `.codex/` configuration only when the directory is **trusted**. On first use, Codex prompts you to trust this repository. This is a security measure — hooks run arbitrary code.

If you cloned this repo and see "untrusted project" warnings:
1. Review the hooks in `hooks.json` and `hooks/` scripts
2. Trust the project when prompted by Codex

## Hooks Overview

| Hook | Handler | Purpose |
|------|---------|---------|
| SessionStart | `hooks/mat_context.py` | Injects MAT context (MAT-1 vs MAT-2, schemas, `CLAUDE.md`) |
| UserPromptSubmit | `hooks/mat_context.py` | Light per-turn reminders and links to skills (no large file dumps) |

Both events run the same Python entrypoint; Codex sets `hook_event_name` on **stdin** so the script can branch.

## Hook JSON contract

All command hooks receive **one JSON object on stdin** and should print **one JSON object on stdout**, then exit **0** on success. See [Codex Hooks](https://developers.openai.com/codex/hooks).

### Common stdin fields (excerpt)

| Field | Meaning |
|-------|---------|
| `session_id` | Session / thread id |
| `cwd` | Session working directory |
| `hook_event_name` | `SessionStart`, `UserPromptSubmit`, etc. |
| `model` | Active model slug |

### SessionStart — extra stdin

| Field | Meaning |
|-------|---------|
| `source` | How the session started: `startup`, `resume`, or `clear` |

### UserPromptSubmit — extra stdin

| Field | Meaning |
|-------|---------|
| `turn_id` | Codex turn id |
| `prompt` | User prompt about to be sent (do not log this from the hook) |

### stdout shape (this repo)

On success, `mat_context.py` emits JSON including:

- `continue`: `true`
- **SessionStart**: `systemMessage` plus `hookSpecificOutput` with `hookEventName: "SessionStart"` and `additionalContext` (same MAT summary text).
- **UserPromptSubmit**: `hookSpecificOutput` with `hookEventName: "UserPromptSubmit"` and short `additionalContext` guardrails only.

Malformed stdin is treated as empty input; the handler still exits **0** and returns **SessionStart**-style output so Codex does not stall.

## Windows: Git Bash and `python3`

`hooks.json` resolves the repo root with `git rev-parse --show-toplevel`, then runs **`python3`** under Bash (Git Bash on Windows, or your platform shell).

- **Git for Windows**: ensure Python is on PATH for the same environment Codex uses when it launches hooks. The official installer option **“Add python.exe to PATH”** usually provides both `python` and `python3` in Git Bash.
- If **`python3` is not found** but `python` works, copy `hooks.json` locally or adjust the command segment from `python3` to `python` (keep the `git rev-parse` wrapper so paths stay repo-root stable).
- **WSL**: prefer running Codex from a WSL workspace if your Windows Python is not visible from Git Bash.

## Directory Layout

```
.codex/
├── README.md              # This file
├── hooks.json             # Hook event → command mappings
├── config.toml.example    # User config snippet for enabling hooks
└── hooks/
    └── mat_context.py     # SessionStart + UserPromptSubmit handler
```

## Relationship to Other Adapters

- **Claude Code**: `.claude/skills/`, `.claude-plugin/plugin.json`
- **Cursor**: `.cursor/skills/`, `adapters/cursor/.cursorrules`
- **Codex**: This directory (`.codex/`)

All adapters point to shared content in `lib/skills/` and follow MAT-16 provider routing.

## References

- [Codex Hooks Documentation](https://developers.openai.com/codex/hooks)
- [Codex AGENTS.md Guide](https://developers.openai.com/codex/guides/agents-md)
- `CLAUDE.md` (orchestrator contract — Codex is a MAT-2 worker, not orchestrator)
