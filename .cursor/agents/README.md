# Cursor Subagents

This directory contains **Cursor native subagents** that follow the [Cursor Subagents](https://cursor.com/docs/subagents) format.

## Official Documentation

- [Cursor Subagents](https://cursor.com/docs/subagents) — Full guide to creating and configuring subagents

## Subagent Format

Each subagent is a Markdown file with YAML frontmatter:

```markdown
---
name: verifier
description: Validates completed work; use after tasks marked done.
model: fast
readonly: false
is_background: false
---

You are a skeptical validator verifying that claimed work actually functions.
```

### Fields

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `name` | No | Filename-derived | Unique identifier (lowercase, hyphens) |
| `description` | No | — | When Agent should delegate to this subagent (critical for auto-invocation) |
| `model` | No | `inherit` | Model to use: `fast`, `inherit`, or specific model ID |
| `readonly` | No | `false` | Restricts write permissions when enabled |
| `is_background` | No | `false` | Enables background execution without blocking |

### Model Options

- **`inherit`** — Uses the parent agent's model
- **`fast`** — Uses a smaller, cost-effective model for speed-prioritized tasks
- **Specific model ID** — References exact models like `claude-opus-4-6` or `gpt-5-mini`

## Subagent Scope and Priority

Subagents are discovered from multiple locations (highest priority first):

| Priority | Location | Scope |
|----------|----------|-------|
| 1 | `.cursor/agents/` | Current project |
| 2 | `.claude/agents/` | Current project (fallback) |
| 3 | `.codex/agents/` | Current project (fallback) |
| 4 | `~/.cursor/agents/` | All your projects |
| 5 | `~/.claude/agents/` | All your projects (fallback) |

## Invocation

Subagents can be invoked:

1. **Automatically** — Agent delegates based on task and description
2. **Explicitly** — `/verifier confirm the auth flow is complete`
3. **Natural language** — `Have the debugger investigate this error`
4. **Parallel** — `Review API changes and update documentation in parallel`

## Architecture

These subagents are **thin stubs** that reference shared definitions in the MAT `agents/` directory:

```
.cursor/agents/           # Cursor native stubs
├── README.md             # This file
├── coder.md              # Implementation subagent
├── researcher.md         # Research subagent
├── reviewer.md           # Code review subagent
├── security.md           # Security analysis subagent
└── tester.md             # Testing subagent

agents/                   # MAT definitions (source of truth)
├── orchestrator.md       # Plans, routes, synthesizes
├── coder.md              # Implements code
├── researcher.md         # Gathers information
├── reviewer.md           # Reviews code
├── security.md           # Security analysis
└── tester.md             # Writes and runs tests
```

## Differences from MAT Agent Definitions

MAT agent definitions (`agents/*.md`) extend this format with:

| MAT Field | Purpose |
|-----------|---------|
| `role` | Agent role classification (`orchestrator`, `worker`, `executor`) |
| `cli` | CLI tool binding for provider routing |
| `allowed_mat_ops` | MAT-2 operation restrictions |
| `tools` | Explicit tool allowlist |
| `temperature` | Default generation temperature |

Cursor uses `readonly` and `is_background` instead of explicit tool lists.

## Best Practices

From the [official documentation](https://cursor.com/docs/subagents):

- **Design focused subagents** — Each should have a single, clear responsibility
- **Invest in descriptions** — The description field drives delegation decisions
- **Keep prompts concise** — Verbose prompts reduce effectiveness and increase latency
- **Version control** — Check `.cursor/agents/` into repositories for team access
- **Start simple** — Begin with 2-3 focused subagents; expand only for distinct use cases

## Anti-Patterns to Avoid

- Vague descriptions like "helps with coding"
- Excessive subagents (50+) with overlapping purposes
- Overly long prompts (2,000+ words)
- Duplicating functionality better served by slash commands
- Generic responsibilities without clear triggers

## See Also

- [`agents/README.md`](../../agents/README.md) — MAT agent definitions (source of truth)
- [`.claude/agents/README.md`](../../.claude/agents/README.md) — Claude Code subagent format
