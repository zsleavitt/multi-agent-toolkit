# ADR 0003: Skill Naming Conventions and Fluency Alignment

## Status

Accepted

## Context

The AI Fluency Insights plugin (`claude-introspection`) scores engineer behavior across dimensions including Planning & Design, Review & PR Hygiene, Testing, and Skills & Automation. The plugin uses **substring pattern matching** on skill names to categorize invocations:

| Dimension | Patterns matched |
|-----------|------------------|
| Planning & Design | `plan`, `brainstorm`, `design`, `architect`, `scope`, `spec`, `sprint` |
| Review & PR Hygiene | `review`, `pr`, `commit`, `diff`, `hygiene` |
| Testing | `test`, `tdd`, `debug`, `diagnos`, `verif`, `ci-triage` |
| Parallelization | `worktree`, `parallel`, `subagent`, `dispatch`, `concurrent` |

Skills that match these patterns contribute to fluency scoring. Skills with generic names (e.g., `invoke`, `run`, `execute`) do not match any dimension and don't build fluency scores despite repeated use.

Additionally, fluency scoring rewards **consistent re-invocation** across sessions. Engineers who use the same 3 skills reliably score higher than those who try 8 skills once each. This means skill names should be:
1. **Memorable** — Easy to recall without looking up documentation
2. **Domain-specific** — Clearly indicate what workflow they automate
3. **Pattern-aligned** — Match fluency dimensions where applicable

## Decision

MAT skills use **domain-specific names** that describe the workflow, not generic "invoke" or "dispatch" terminology.

### Skill Architecture

```
/develop <task>        → Coder agent (Codex) implements via `codex.implement`
/review-pr <target>    → Reviewer agent directly (matches "review" + "pr")
/test <scope>          → Tester agent directly (matches "test")
/diagnose <issue>      → Debugging workflow (matches "diagnos")
/plan <goal>           → Planning without execution (matches "plan")
/security-scan <scope> → Security agent directly
```

### Why not `/invoke-agent` or `/dispatch-agents`?

1. **No fluency pattern match** — "invoke" and "dispatch" (without parallelization context) don't contribute to scoring
2. **Cognitive overhead** — `/invoke-agent coder "implement X"` requires remembering both the skill AND the agent name
3. **Redundant with domain skills** — `/develop` already "dispatches" the team; a separate dispatch skill adds no value
4. **Poor discoverability** — Generic names don't suggest when to use them

### Naming Guidelines

| Guideline | Good | Avoid |
|-----------|------|-------|
| Use action verbs | `/develop`, `/review-pr`, `/test` | `/agent`, `/tool`, `/run` |
| Match fluency patterns | `/diagnose` (matches `diagnos`) | `/debug-helper` |
| Be specific | `/review-pr` | `/review` (ambiguous: code? PR? design?) |
| Indicate scope | `/security-scan` | `/security` (noun, not action) |

## Consequences

### Positive

- Skills contribute to fluency scoring where patterns align
- Engineers build muscle memory for domain-specific commands
- Clear mental model: `/develop` = team, others = single specialist
- Future skills follow established naming conventions

### Negative

- Less flexibility than generic `/invoke-agent <any-agent>`
- Adding new workflows requires new skills (can't just pass agent name)
- Some agents may not have dedicated skills initially

### Mitigations

- The runtime layer (`mat_runtime`) remains available for programmatic access
- New skills can be added incrementally as workflows stabilize
- Agent definitions document capabilities independent of skill availability

## References

- AI Fluency Insights plugin: `~/org/claude-code/plugins/claude-introspection/`
- MAT-19: Original skill integration ticket
- ADR 0002: CLI delegation model (skills invoke CLIs, not APIs)
