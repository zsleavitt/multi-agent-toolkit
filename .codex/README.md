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
| PreToolUse | `hooks/mat_guardrails.py` | Optional Bash guardrails (`off` / `warn` / `enforce`) — see below |
| PostToolUse | `hooks/mat_guardrails.py` | Optional Bash non-zero exit hint (`warn` only) |

`mat_context.py` branches on `hook_event_name` from stdin. `mat_guardrails.py` is **off by default** (exit `0`, empty stdout) so there is no behavior change until you configure it.

### Optional guardrails (PreToolUse / PostToolUse)

**Configuration** (first match wins):

1. `MAT_CODEX_GUARDRAILS_MODE` — `off` (default), `warn`, or `enforce`
2. `.codex/guardrails.toml` — copy from `guardrails.toml.example` and set `[guardrails] mode`

`enforce` uses **PreToolUse** `permissionDecision: deny` only for obviously destructive **Bash** patterns (e.g. `rm` against `/`, `mkfs`, `dd of=/dev/`, fork-bomb idiom, `curl|sh`-style pipes). It does **not** try to block normal `git` read-only use or file edits via `apply_patch` — those remain governed by `CLAUDE.md` / MAT-1 vs MAT-2 guidance from SessionStart.

**PostToolUse** only adds a **systemMessage** when `mode = warn` and the last **Bash** command reports a non-zero exit code.

**Limitations (OpenAI / Codex):** hooks are **not a full sandbox** — they cannot intercept every tool path, and behavior can evolve with Codex releases. Treat guardrails as a safety net, not authorization. See [Codex Hooks — PreToolUse](https://developers.openai.com/codex/hooks#pretooluse).

**Matchers:** `hooks.json` registers `PreToolUse` / `PostToolUse` with matchers `Bash` and `apply_patch` (Codex treats `Edit` / `Write` as `apply_patch` for matching). The Python script only evaluates **Bash** for guardrail logic; `apply_patch` entries satisfy matcher wiring with minimal overhead when mode is `off`. To add **MCP** matchers (e.g. `mcp__server__tool`), duplicate a hook block and set `matcher` per [Codex matcher patterns](https://developers.openai.com/codex/hooks#matcher-patterns); extend `mat_guardrails.py` if you need MCP-specific checks.

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
├── README.md                  # This file
├── hooks.json                 # Hook event → command mappings
├── config.toml.example        # User config snippet for enabling hooks
├── guardrails.toml.example    # Optional guardrails mode (copy to guardrails.toml)
└── hooks/
    ├── mat_context.py         # SessionStart + UserPromptSubmit
    └── mat_guardrails.py      # Optional PreToolUse / PostToolUse guardrails
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
