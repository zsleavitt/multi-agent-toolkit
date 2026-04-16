# Agent Definition Format

This document specifies the format for defining agents in the Multi-Agent Toolkit. Agent definitions are Markdown files with YAML frontmatter that describe an agent's identity, capabilities, and behavior.

## File format

Agent definitions use Markdown with YAML frontmatter:

```markdown
---
name: coder
description: Implements code changes based on specifications
role: worker
cli: codex
allowed_mat_ops:
  - codex.implement
  - codex.test
  - codex.refactor
tools:
  - read
  - write
  - bash
---

You are a code implementation agent. Your role is to...

[System prompt content here]
```

## Location

Agent definitions live in the `agents/` directory:

```
multi-agent-toolkit/
├── agents/
│   ├── orchestrator.md
│   ├── coder.md
│   ├── researcher.md
│   ├── reviewer.md
│   └── tester.md
```

## Frontmatter schema

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Unique identifier for the agent (lowercase, no spaces) |
| `description` | string | Yes | Human-readable description of the agent's purpose |
| `role` | enum | Yes | Agent role: `orchestrator`, `worker`, or `executor` |
| `cli` | string | Yes | CLI tool binding (must match MAT-16 agent config) |
| `allowed_mat_ops` | string[] | No | MAT-2 operations this agent can perform |
| `tools` | string[] | No | Tools the agent has access to |
| `timeout_ms` | integer | No | Default timeout for this agent |
| `temperature` | number | No | Default temperature (0.0–2.0) |

### Field details

#### `name`
- Must be unique across all agents
- Lowercase alphanumeric with hyphens: `^[a-z][a-z0-9-]*$`
- Max 64 characters

#### `role`
One of:
- `orchestrator` — Plans, decomposes, routes, synthesizes
- `worker` — Executes scoped tasks (implement, test, refactor)
- `executor` — Runs constrained operations (git, CLI)

#### `cli`
References a CLI tool from MAT-16:
- `claude` — Claude Code CLI
- `codex` — OpenAI Codex CLI
- `gemini` — Google Gemini CLI
- `cursor`, `aider`, `continue`, `custom`

#### `allowed_mat_ops`
Array of MAT-2 operations (from `schemas/codex-code-exec/v1/manifest.json`):
- `codex.implement`
- `codex.test`
- `codex.refactor`
- `codex.diagnose`
- `codex.review`

Omit or empty array means no MAT-2 restrictions.

#### `tools`
Array of tool names the agent can use:
- `read` — Read files
- `write` — Write files
- `edit` — Edit files
- `bash` — Execute shell commands
- `glob` — Search for files
- `grep` — Search file contents
- `agent` — Spawn sub-agents
- `mcp` — Use MCP tools

## Body content

The Markdown body after the frontmatter is the agent's **system prompt**. This defines:
- The agent's persona and communication style
- Specific instructions for handling tasks
- Constraints and guardrails
- Output format expectations

### Example body

```markdown
You are a code implementation agent specializing in clean, well-tested code.

## Your responsibilities
- Implement features based on specifications
- Write unit tests for new code
- Follow existing code patterns and conventions

## Constraints
- Never modify files outside the specified scope
- Always run tests before marking work complete
- Ask for clarification if requirements are ambiguous

## Output format
When completing a task, summarize:
1. Files modified
2. Tests added/updated
3. Any concerns or follow-up items
```

## Core agents

The toolkit provides 5 core agent definitions:

| Agent | Role | CLI | Purpose |
|-------|------|-----|---------|
| `orchestrator` | orchestrator | claude | Planning, routing, synthesis |
| `coder` | worker | codex | Code implementation |
| `researcher` | executor | gemini | Information gathering, research |
| `reviewer` | worker | claude | Code review, analysis |
| `tester` | worker | codex | Test writing and execution |

## Validation

Agent definitions are validated by `scripts/validate_agent_definitions.py`:

1. **Frontmatter schema** — Required fields present and typed correctly
2. **MAT-2 ops** — `allowed_mat_ops` references valid operations from manifest
3. **CLI binding** — `cli` references valid tool from MAT-16 schema
4. **Name uniqueness** — No duplicate agent names

Run validation:

```bash
source .venv/bin/activate
python scripts/validate_agent_definitions.py
```

## Integration with MAT-16

Agent definitions work alongside MAT-16 agent configuration:

- **MAT-16** (`schemas/provider-config/v1/`) — Which CLI handles which role
- **Agent definitions** (`agents/`) — Individual agent personas and prompts

A typical setup:
1. MAT-16 config maps `worker` role to `codex` CLI
2. `agents/coder.md` defines the `coder` agent with `role: worker`
3. Orchestrator routes implementation tasks to `coder`
4. `codex` CLI executes with the coder's system prompt

## Extending

To add a custom agent:

1. Create `agents/my-agent.md` with frontmatter + prompt
2. Run `python scripts/validate_agent_definitions.py`
3. Reference in MAT-16 config or routing rules
