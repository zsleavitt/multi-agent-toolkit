# Superpowers + MAT Integration

This document describes how to chain the Superpowers plugin with Multi-Agent Toolkit (MAT) components for orchestrated development workflows.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    SUPERPOWERS (Workflow Layer)                  │
│                                                                 │
│  brainstorming → writing-plans → subagent-driven-development   │
│                                    ↓                            │
│                         dispatches tasks to...                  │
└─────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────┐
│                    MAT (Execution Layer)                         │
│                                                                 │
│  /develop skill                                                 │
│       ↓                                                         │
│  orchestrator.md agent                                          │
│       ↓                                                         │
│  routes to: coder | tester | reviewer | researcher              │
└─────────────────────────────────────────────────────────────────┘
```

## Workflow Stages

### Stage 1: Brainstorming (Superpowers)

Use `superpowers:brainstorming` to refine requirements before planning.

```
User: I want to implement MAT-42 (Define Crew schema)
Claude: [invokes superpowers:brainstorming]
→ Explores design space
→ Identifies key decisions
→ Outputs refined requirements
```

### Stage 2: Planning (Superpowers)

Use `superpowers:writing-plans` to create a structured implementation plan.

```
Claude: [invokes superpowers:writing-plans]
→ Creates plan file: docs/superpowers/plans/YYYY-MM-DD-feature-name.md
→ Breaks work into discrete tasks
→ Each task has clear acceptance criteria
```

### Stage 3: Execution (Superpowers + MAT)

Use `superpowers:subagent-driven-development` with MAT agents as implementers.

```
Claude: [invokes superpowers:subagent-driven-development]
→ For each task:
   → Dispatch MAT coder agent (or /develop skill)
   → Spec compliance review
   → Code quality review
   → Mark complete
```

### Stage 4: Completion (Superpowers)

Use `superpowers:finishing-a-development-branch` for final review and PR.

```
Claude: [invokes superpowers:finishing-a-development-branch]
→ Final verification
→ Commit cleanup
→ PR creation
```

## Integration Points

### MAT Agents as Superpowers Subagents

When superpowers dispatches an "implementer subagent", it can invoke MAT agents:

```markdown
# In implementer-prompt.md context:

You are implementing Task N of the plan.

Use the MAT coder agent pattern:
- Follow TDD (superpowers:test-driven-development)
- Commit after each logical change
- Self-review before reporting done

Task: [full task text from plan]
Context: [relevant codebase context]
```

### /develop as Implementation Entry Point

For complex tasks that need orchestration:

```bash
# Instead of direct implementation, invoke /develop
/develop "Implement the Crew schema with validation"
```

The orchestrator will decompose and route to specialized agents.

## Example: Implementing MAT-42 (Crew Schema)

### 1. Brainstorm
```
/brainstorm Define the Crew schema for MAT - a named agent collection with shared goals
```

### 2. Plan
```
/plan Create implementation plan for MAT-42 Crew schema
```

Plan output → `docs/superpowers/plans/2026-04-20-crew-schema.md`

### 3. Execute
```
/execute-plan docs/superpowers/plans/2026-04-20-crew-schema.md
```

Each task dispatched to MAT agents.

### 4. Finish
```
/finish
```

Creates PR with all changes.

## Configuration

### ai-team.repo.json

Ensure your repo profile supports both MAT and Superpowers:

```json
{
  "work_item_source": {
    "adapter": "github_issues",
    "github_issues": {
      "owner": "your-org",
      "repo": "your-repo"
    }
  },
  "orchestration": {
    "branch_template": "mat-{{id}}",
    "workflow": "superpowers-mat"
  }
}
```

## When to Use Each Component

| Scenario | Use |
|----------|-----|
| Quick bug fix | `/develop` directly |
| New feature (complex) | Full superpowers workflow |
| Code review only | `/review-pr` |
| Research/exploration | MAT researcher agent |
| Multi-file refactor | superpowers:subagent-driven-development |

## See Also

- [Superpowers Plugin](https://github.com/anthropics/superpowers)
- [MAT Agent Definitions](../../../agents/)
- [MAT Skills](../../../lib/skills/)
