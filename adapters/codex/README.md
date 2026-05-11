# Codex Adapter

This adapter integrates [OpenAI Codex](https://openai.com/codex) as a **MAT-2 worker** in the Multi-Agent Toolkit. Codex handles code implementation, testing, refactoring, and diagnosis — while Claude Code remains the orchestrator for planning, routing, and git operations (MAT-1).

## Role in MAT

| Role | Agent | Responsibility |
|------|-------|----------------|
| **Orchestrator** | Claude Code | Plan, decompose, route tasks, synthesize results, emit MAT-1 git requests |
| **MAT-2 Worker** | Codex | Implement, test, refactor, diagnose, review — scoped code operations |
| **Git Executor** | Gemini (optional) | Execute allowlisted git ops from MAT-1 requests |

Codex receives context about this split via **SessionStart** hooks that inject MAT boundaries into every session.

## Installation

Run the setup script from the repository root:

**macOS / Linux**

```bash
bin/setup
```

**Windows (PowerShell)**

```powershell
.\bin\setup.ps1
```

Setup will:
1. Print Codex user config guidance (enable `codex_hooks` in `~/.codex/config.toml`)
2. Optionally merge the feature flag idempotently with `--apply`
3. Remind you to run `codex auth` and trust the `.codex/` project directory

For detailed hook configuration, see [`.codex/README.md`](../../.codex/README.md).

## Configuration Files

| File | Purpose |
|------|---------|
| `.codex/hooks.json` | Hook event → command mappings |
| `.codex/config.toml.example` | User config snippet (`codex_hooks = true`) |
| `.codex/guardrails.toml.example` | Optional PreToolUse/PostToolUse guardrails |
| `.codex/hooks/mat_context.py` | SessionStart + UserPromptSubmit handler |
| `.codex/hooks/mat_guardrails.py` | Optional Bash guardrails (off by default) |

## MAT-2 Schema

Codex worker requests and responses follow the **MAT-2** schema:

```
schemas/codex-code-exec/v1/
├── README.md
├── request.schema.json
└── response.schema.json
```

| Operation | Description |
|-----------|-------------|
| `codex.implement` | Write or modify code |
| `codex.test` | Write and run tests |
| `codex.refactor` | Restructure existing code |
| `codex.diagnose` | Debug and root-cause analysis |
| `codex.review` | Structured code review |

The `mat_runtime` module routes MAT-2 requests to the configured worker CLI. See [`mat_runtime/`](../../mat_runtime/) and [`schemas/provider-config/v1/`](../../schemas/provider-config/v1/).

## Trust Model

Codex loads project-local `.codex/` hooks only when the directory is **trusted**. On first use in a repository, Codex prompts for trust confirmation. This is a security measure — hooks execute arbitrary code.

Review `.codex/hooks.json` and `.codex/hooks/*.py` before trusting.

## Differences from Claude Code Adapter

| Aspect | Claude Code | Codex |
|--------|-------------|-------|
| Role | Orchestrator (MAT-1 routing) | Worker (MAT-2 implementation) |
| Config location | `.claude/`, `~/.claude/` | `.codex/`, `~/.codex/` |
| Skill discovery | `.claude/skills/` → plugin manifest | `.agents/skills/` (SKILL.md format) |
| Hook system | Claude Code hooks | Codex command hooks |
| Agent instructions | `CLAUDE.md` | `AGENTS.md` |

## Cross-References

- [`.codex/README.md`](../../.codex/README.md) — Detailed hook configuration, JSON contract, Windows notes
- [`adapters/claude-code/README.md`](../claude-code/README.md) — Claude Code plugin setup
- [`adapters/cursor/README.md`](../cursor/README.md) — Cursor personal skills setup
- [`CLAUDE.md`](../../CLAUDE.md) — Orchestrator contract and MAT schema overview
- [`CURSOR_HANDOFF.md`](../../CURSOR_HANDOFF.md) — Cursor-specific pickup steps

## External Documentation

- [Codex Hooks](https://developers.openai.com/codex/hooks) — Hook events, matchers, JSON contract
- [Codex AGENTS.md Guide](https://developers.openai.com/codex/guides/agents-md) — Agent instructions file format
- [Codex Skills](https://developers.openai.com/codex/skills) — SKILL.md format and discovery
- [Codex Plugins](https://developers.openai.com/codex/plugins) — Plugin bundling (skills, apps, MCP)

## Troubleshooting

### Hooks not firing

1. Verify `codex_hooks = true` in `~/.codex/config.toml`
2. Trust the repository when prompted by Codex
3. Check `codex auth` status

### Python not found (Windows)

Hooks use `python3` via Git Bash. Ensure Python is on PATH for the Git Bash environment, or adjust `.codex/hooks.json` to use `python` instead.

### Guardrails blocking safe commands

Set `MAT_CODEX_GUARDRAILS_MODE=off` or remove `.codex/guardrails.toml`. The default is `off`.

## See Also

- [`schemas/codex-code-exec/v1/`](../../schemas/codex-code-exec/v1/) — MAT-2 request/response schemas
- [`mat_runtime/`](../../mat_runtime/) — Runtime adapter for CLI routing
- [`agents/`](../../agents/) — Agent role definitions
