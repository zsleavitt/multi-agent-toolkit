---
name: develop
description: Orchestrated development workflow — plans, implements, and coordinates the agent team. Use when implementing features, fixing bugs, or refactoring code that needs coordination across multiple agents.
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

The orchestrator will decompose the task, route to appropriate agents (coder, tester, reviewer), and synthesize results.
