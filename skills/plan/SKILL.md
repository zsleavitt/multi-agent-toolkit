---
name: plan
description: Plan and decompose tasks without executing — architecture and design phase
version: 1.0.0
---

# Plan

Invokes the orchestrator agent in planning-only mode to decompose tasks, design architecture, and create work breakdown structures without executing any changes.

## Usage

```
/plan <goal>
```

## Examples

### Plan a feature
```
/plan Design the architecture for adding OAuth2 authentication
```

### Decompose a task
```
/plan Break down the migration from REST to GraphQL into phases
```

### Architecture review
```
/plan What would it take to make this service horizontally scalable?
```

### Sprint planning
```
/plan Create a work breakdown for implementing the notification system
```

## What plan produces

```
## Plan: [Goal Summary]

### Overview
[High-level approach]

### Work Items
1. [Item 1] — Route to: coder
   - Description: [What needs to be done]
   - Estimate: [Complexity]

2. [Item 2] — Route to: tester
   - Description: [What needs to be done]
   - Depends on: Item 1

### Dependencies
[Diagram or list of dependencies]

### Risks
[Potential issues and mitigations]

### Next Steps
[Recommended order of execution]
```

## When to use `/plan` vs `/develop`

| Scenario | Use |
|----------|-----|
| Just want a plan, not execution | `/plan` |
| Plan and execute in one workflow | `/develop` |
| Understand scope before committing | `/plan` then `/develop` |
| Architecture discussion | `/plan` |

## Instructions

When the user invokes this skill:

1. Parse the planning goal from the input after `/plan`

2. Invoke the orchestrator in planning mode:
   ```bash
   python skills/plan/plan.py "<goal>" --repo-root "$(pwd)"
   ```

3. Present the plan:
   - Work breakdown structure
   - Dependencies between items
   - Routing recommendations
   - Risk assessment

Note: This skill produces a plan only — no code changes are made. Use `/develop` to execute.

## Implementation note

This skill uses `codex.diagnose` as the underlying operation because MAT-2 schema 1.2.0 lacks a dedicated `codex.plan` op. The diagnose op is read-only analysis, making it appropriate for planning tasks that should not modify files. A future MAT-2 schema version (1.3.0+) may introduce a semantic `codex.plan` op.

## See also

- `/develop` — Execute after planning
- ADR 0003 — Skill naming conventions (matches `plan` fluency pattern)
