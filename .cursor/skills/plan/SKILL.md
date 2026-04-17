---
name: plan
description: Plan and decompose tasks without executing — architecture and design phase. Use when designing architecture, breaking down complex work, or creating implementation strategies.
---

# Plan

Plan and decompose tasks without executing — architecture and design phase.

## Usage

```
/plan <goal>
```

## Examples

- `/plan Design the architecture for adding OAuth2 authentication`
- `/plan Break down the migration from REST to GraphQL into phases`
- `/plan Create a work breakdown for implementing the notification system`

## Instructions

1. Parse the planning goal from the input
2. Run the skill script:
   ```bash
   python lib/skills/plan/plan.py "<goal>" --repo-root "$(pwd)"
   ```
3. Present: work breakdown, dependencies, routing recommendations, risks

This produces a plan only — no code changes. Use `/develop` to execute.

For complete documentation, see `lib/skills/plan/instructions.md`.
