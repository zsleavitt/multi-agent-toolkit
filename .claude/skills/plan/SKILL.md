---
name: plan
description: Plan and decompose tasks without executing — architecture and design phase. Use when you need a work breakdown before implementation.
version: 1.0.0
allowed-tools: Bash(python *)
---

# Plan

Invokes the orchestrator in planning-only mode to decompose tasks and create work breakdown structures without executing any changes.

For complete documentation, see [instructions.md](../../../lib/skills/plan/instructions.md).

## Quick Start

```
/plan <goal>
```

## Examples

- `/plan Design the architecture for adding OAuth2 authentication`
- `/plan Break down the migration from REST to GraphQL into phases`
- `/plan Create a work breakdown for implementing the notification system`

## Execution

Run the skill script:

```bash
python lib/skills/plan/plan.py "$ARGUMENTS" --repo-root "$(pwd)"
```

Produces a plan only — no code changes are made. Use `/develop` to execute.
