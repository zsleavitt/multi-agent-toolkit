---
name: develop
description: Implementation workflow via OpenAI Codex (coder agent). Use when implementing features, fixing bugs, or refactoring scoped tasks. For planning-only decomposition, use the plan skill.
version: 1.0.0
allowed-tools: Bash(python *)
---

# Develop

Initiates an orchestrated development workflow using the multi-agent toolkit.

For complete documentation, see [instructions.md](../../../lib/skills/develop/instructions.md).

## Quick Start

```
/develop <task description>
```

## Examples

- `/develop Add a fibonacci function to src/utils/math.py with input validation`
- `/develop Fix the null pointer exception in UserService.getProfile`
- `/develop Refactor the authentication module to use dependency injection`

## Execution

Run the skill script:

```bash
python lib/skills/develop/develop.py "$ARGUMENTS" --repo-root "$(pwd)"
```

The **coder** agent runs **Codex** (`codex.implement`) against the task. Use **plan** for decomposition without implementation, and **review-pr** for Claude-based review.
