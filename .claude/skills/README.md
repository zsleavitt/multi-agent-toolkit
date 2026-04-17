# Claude Code Skills

This directory contains **Claude Code native skills** that follow the [Claude Code custom slash commands](https://docs.anthropic.com/en/docs/claude-code/slash-commands#custom-slash-commands) format.

## Official Documentation

- [Custom Slash Commands](https://docs.anthropic.com/en/docs/claude-code/slash-commands#custom-slash-commands) — How to create and structure custom commands
- [Claude Code Overview](https://docs.anthropic.com/en/docs/claude-code/overview) — General Claude Code documentation

## Skill Format

Each skill lives in its own directory with a `SKILL.md` file:

```
.claude/skills/
├── develop/
│   └── SKILL.md
├── diagnose/
│   └── SKILL.md
└── ...
```

### SKILL.md Structure

Claude Code skills use YAML frontmatter followed by markdown content:

```markdown
---
name: skill-name
description: Brief description shown in skill list
version: 1.0.0
---

# Skill Name

Full documentation and instructions...
```

### Frontmatter Fields

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Skill identifier (should match folder name) |
| `description` | Yes | Brief description for discovery and help |
| `version` | No | Semantic version for tracking changes |

## Architecture

These skills are **thin stubs** that reference shared implementations in `lib/skills/`. This design:

- Maintains a single source of truth for skill logic
- Allows platform-specific frontmatter and formatting
- Keeps skills discoverable in Claude Code's expected location

```
.claude/skills/<name>/SKILL.md    → Platform stub (frontmatter + quick reference)
lib/skills/<name>/instructions.md → Shared full documentation
lib/skills/<name>/<name>.py       → Shared Python implementation
```

## Invocation

Skills are invoked as slash commands in Claude Code:

```
/develop Add a fibonacci function to src/utils/math.py
/ticket create "Fix login bug" --priority P0
/review-pr Review staged changes for security issues
```

## See Also

- [`lib/skills/README.md`](../../lib/skills/README.md) — Shared skill library documentation
- [`.cursor/skills/README.md`](../../.cursor/skills/README.md) — Cursor-specific skill format
