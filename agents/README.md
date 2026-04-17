# MAT Agent Definitions

This directory contains **Multi-Agent Toolkit (MAT) agent definitions** — provider-agnostic agent specifications that can be bound to different CLI tools.

## Format

Agent definitions are Markdown files with YAML frontmatter:

```markdown
---
name: coder
description: Implements code changes, writes new features, and fixes bugs
role: worker
cli: codex
allowed_mat_ops:
  - codex.implement
  - codex.refactor
tools:
  - read
  - write
  - edit
  - bash
temperature: 0.2
---

You are a code implementation agent...
```

## Frontmatter Fields

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Unique agent identifier (lowercase, hyphens allowed) |
| `description` | Yes | Human-readable description of the agent's purpose |
| `role` | Yes | `orchestrator` (plan/route), `worker` (execute tasks), or `executor` (constrained ops) |
| `cli` | Yes | CLI tool binding: `claude`, `codex`, `gemini`, `cursor`, `aider`, `continue`, `custom` |
| `allowed_mat_ops` | No | MAT-2 operations allowed (e.g., `codex.implement`, `codex.test`) |
| `tools` | No | Tools the agent can use: `read`, `write`, `edit`, `bash`, `glob`, `grep`, `agent`, `mcp`, `web` |
| `timeout_ms` | No | Default timeout in milliseconds (1s–1h) |
| `temperature` | No | Default temperature for generation (0.0–2.0) |

## Core Agents

| Agent | Role | CLI | Purpose |
|-------|------|-----|---------|
| `orchestrator` | orchestrator | claude | Plan, decompose, route, synthesize |
| `coder` | worker | codex | Implement code, fix bugs, refactor |
| `researcher` | executor | gemini | Gather information, explore codebases |
| `reviewer` | worker | claude | Code review, quality analysis |
| `security` | worker | claude | Security analysis, vulnerability scanning |
| `tester` | worker | codex | Write and run tests |

## Schema Validation

Agent definitions are validated against the MAT-17 schema:

```bash
source .venv/bin/activate
python scripts/validate_agent_definitions.py
```

See `schemas/agent-definition/v1/README.md` for schema details.

## Provider-Specific Agents

MAT agent definitions are the **source of truth** for agent behavior. Provider-specific versions may exist for native discovery:

| Provider | Location | Purpose |
|----------|----------|---------|
| Claude Code | `.claude/agents/` | Native subagent discovery |
| Cursor | `.cursor/agents/` (if supported) | Native agent discovery |

## Architecture

```
agents/                           # MAT definitions (source of truth)
├── README.md                     # This file
├── orchestrator.md               # Plans, routes, synthesizes
├── coder.md                      # Implements code
├── researcher.md                 # Gathers information
├── reviewer.md                   # Reviews code
├── security.md                   # Security analysis
└── tester.md                     # Writes and runs tests

.claude/agents/                   # Claude Code native stubs
├── README.md                     # Claude Code format docs
└── *.md                          # Native subagent definitions

schemas/agent-definition/v1/      # MAT-17 schema
├── agent-frontmatter.schema.json # JSON Schema
└── examples/                     # Validation fixtures
```

## Relationship to Claude Code Subagents

MAT agent definitions extend Claude Code's native subagent format with:

- **`role`** — Agent role classification (`orchestrator`, `worker`, `executor`)
- **`cli`** — CLI tool binding for provider routing
- **`allowed_mat_ops`** — MAT-2 operation restrictions

Claude Code's native format includes fields not in MAT:

- **`permissionMode`** — Permission handling (`default`, `auto`, `bypassPermissions`, etc.)
- **`memory`** — Persistent memory scope (`user`, `project`, `local`)
- **`hooks`** — Lifecycle hooks for the subagent
- **`mcpServers`** — MCP servers scoped to the subagent

For Claude Code native subagent documentation, see:
- [Create custom subagents](https://code.claude.com/docs/en/sub-agents)
- `.claude/agents/README.md` (provider-specific docs)

## See Also

- `schemas/agent-definition/v1/README.md` — MAT-17 schema specification
- `schemas/provider-config/v1/README.md` — MAT-16 provider configuration
- `docs/agent-definition-format.md` — Full specification (if exists)
