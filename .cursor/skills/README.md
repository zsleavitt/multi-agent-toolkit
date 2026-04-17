# Cursor Skills

This directory contains **Cursor native skills** that follow the [Cursor Skills](https://docs.cursor.com/context/skills) format.

## Official Documentation

- [Cursor Skills Reference](https://docs.cursor.com/context/skills) — How to create and structure skills
- [Cursor Rules vs Skills](https://docs.cursor.com/context/rules-for-ai) — When to use rules vs skills

## Skill Format

Each skill lives in its own directory with a `SKILL.md` file:

```
.cursor/skills/
├── develop/
│   └── SKILL.md
├── diagnose/
│   └── SKILL.md
└── ...
```

### SKILL.md Structure

Cursor skills use YAML frontmatter followed by markdown content:

```markdown
---
name: skill-name
description: Brief description — used by the agent to judge relevance
disable-model-invocation: true
---

# Skill Name

Full documentation and instructions...
```

### Frontmatter Fields

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Skill identifier (must match folder name) |
| `description` | Yes | Used by agent for relevance matching — include "Use when..." guidance |
| `disable-model-invocation` | No | When `true`, skill is only invoked via explicit slash command |
| `compatibility` | No | List of environment requirements (MCP servers, config files, etc.) |

### When to Use `disable-model-invocation`

Set to `true` only for skills that should NEVER be auto-invoked — for example, destructive operations or administrative commands where explicit user intent is critical.

Most skills should omit this field (defaults to `false`) to allow:
- **Natural language invocation** — "create a ticket for this bug" triggers the ticket skill
- **Programmatic invocation** — The `Skill` tool can invoke the skill
- **Explicit slash invocation** — `/ticket create X` still works

### Compatibility Field

For skills with environment dependencies, list requirements:

```yaml
compatibility:
  - ai-team.repo.json configuration file in repo root
  - Configured MCP server for your ticket provider
```

## Architecture

These skills are **thin stubs** that reference shared implementations in `lib/skills/`. This design:

- Maintains a single source of truth for skill logic
- Allows platform-specific frontmatter and formatting
- Keeps skills discoverable in Cursor's expected location

```
.cursor/skills/<name>/SKILL.md    → Platform stub (frontmatter + quick reference)
lib/skills/<name>/instructions.md → Shared full documentation
lib/skills/<name>/<name>.py       → Shared Python implementation
```

## Invocation

Skills are invoked as slash commands in Cursor:

```
/develop Add a fibonacci function to src/utils/math.py
/ticket create "Fix login bug" --priority P0
/review-pr Review staged changes for security issues
```

Note: Subcommands (like `create` in `/ticket create`) are arguments passed in the same message, not separate slash commands.

## See Also

- [`lib/skills/README.md`](../../lib/skills/README.md) — Shared skill library documentation
- [`.claude/skills/README.md`](../../.claude/skills/README.md) — Claude Code-specific skill format
