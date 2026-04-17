# Claude Code Subagents

This directory contains **Claude Code native subagents** that follow the [Custom Subagents](https://code.claude.com/docs/en/sub-agents) format.

## Official Documentation

- [Create custom subagents](https://code.claude.com/docs/en/sub-agents) — Full guide to creating and configuring subagents
- [Agent teams](https://code.claude.com/docs/en/agent-teams) — Coordinating multiple agents across sessions
- [Tools reference](https://code.claude.com/docs/en/tools-reference) — Available tools for subagents

## Subagent Format

Each subagent is a Markdown file with YAML frontmatter:

```markdown
---
name: code-reviewer
description: Reviews code for quality and best practices
tools: Read, Glob, Grep, Bash
model: sonnet
---

You are a code reviewer. When invoked, analyze the code and provide
specific, actionable feedback on quality, security, and best practices.
```

### Required Fields

| Field | Description |
|-------|-------------|
| `name` | Unique identifier using lowercase letters and hyphens |
| `description` | When Claude should delegate to this subagent |

### Optional Fields

| Field | Description |
|-------|-------------|
| `tools` | Tools the subagent can use (inherits all if omitted) |
| `disallowedTools` | Tools to deny from inherited set |
| `model` | Model to use: `sonnet`, `opus`, `haiku`, full ID, or `inherit` |
| `permissionMode` | Permission handling: `default`, `acceptEdits`, `auto`, `dontAsk`, `bypassPermissions`, `plan` |
| `maxTurns` | Maximum agentic turns before stopping |
| `skills` | Skills to preload into context |
| `mcpServers` | MCP servers scoped to this subagent |
| `hooks` | Lifecycle hooks for the subagent |
| `memory` | Persistent memory scope: `user`, `project`, or `local` |
| `background` | Set `true` to always run as background task |
| `effort` | Effort level: `low`, `medium`, `high`, `xhigh`, `max` |
| `isolation` | Set `worktree` for git worktree isolation |
| `color` | Display color: `red`, `blue`, `green`, `yellow`, `purple`, `orange`, `pink`, `cyan` |
| `initialPrompt` | Auto-submitted as first turn when running as main agent |

## Subagent Scope and Priority

Subagents are discovered from multiple locations (highest priority first):

| Priority | Location | Scope |
|----------|----------|-------|
| 1 | Managed settings | Organization-wide |
| 2 | `--agents` CLI flag | Current session |
| 3 | `.claude/agents/` | Current project |
| 4 | `~/.claude/agents/` | All your projects |
| 5 | Plugin `agents/` | Where plugin is enabled |

## Invocation

Subagents can be invoked:

1. **Automatically** — Claude delegates based on task and description
2. **By mention** — `@"agent-name (agent)" do something`
3. **Session-wide** — `claude --agent agent-name`

## Architecture

These subagents are **thin stubs** that reference shared definitions in the MAT `agents/` directory:

```
.claude/agents/           # Claude Code native stubs
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
| `temperature` | Default generation temperature |

These Claude Code stubs omit MAT-specific fields and use only the fields Claude Code understands.

## Best Practices

From the [official documentation](https://code.claude.com/docs/en/sub-agents#example-subagents):

- **Design focused subagents** — Each should excel at one specific task
- **Write detailed descriptions** — Claude uses the description to decide when to delegate
- **Limit tool access** — Grant only necessary permissions for security and focus
- **Check into version control** — Share project subagents with your team

## See Also

- [`agents/README.md`](../../agents/README.md) — MAT agent definitions (source of truth)
- [Context window visualization](https://code.claude.com/docs/en/context-window) — How subagents preserve context
- [Hooks documentation](https://code.claude.com/docs/en/hooks) — Lifecycle hooks for subagents
