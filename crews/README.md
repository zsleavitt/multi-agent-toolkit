# Crews

This directory contains Crew definitions — JSON files that define named collections of agents with shared goals and routing configuration.

## File Format

Each crew is a JSON file following the schema at `schemas/crew/v1/crew.schema.json`. The filename must match the `name` field (e.g. `dev-crew.json` → `"name": "dev-crew"`).

## Crew Definitions

| File | Purpose |
|------|---------|
| `dev-crew.json` | Full-stack development with TDD (coder, tester, reviewer) |
| `review-crew.json` | Code review and security analysis (coder, reviewer, security) |

## Composition Patterns

### Dev crew vs review crew

- **Dev crew** (`dev-crew.json`): Use for implementation workflows — capability routing on `tags` and `languages` so tasks land on the best-fit agent, with tester and reviewer in the rotation.
- **Review crew** (`review-crew.json`): Use for post-implementation review — capability routing on `domain` and `tags`, with security given higher priority for security-sensitive tasks.

### Routing strategies

| Strategy | When to use |
|----------|-------------|
| `round-robin` | Equal workload across agents; no specialization needed |
| `capability` | Match tasks to agents by specialization (`match_on` fields) |
| `priority` | Prefer agents with higher `priority` overrides |
| `random` | Load balancing without strict ordering |

Set `fallback` when capability matching finds no candidate (e.g. `"fallback": "round-robin"`).

### Agent references

Agents can be listed as plain strings or objects with per-crew overrides:

```json
"agents": [
  "coder",
  {
    "name": "reviewer",
    "timeout_ms": 120000,
    "priority": 50,
    "required_capabilities": ["security"]
  }
]
```

Use string refs when defaults suffice; use object refs for timeouts, routing priority, or required capabilities.

## Runtime Registry

Discover crews and mutate membership at runtime with `CrewRegistry`. Mutations are **in-memory only** until you call `save()`.

```python
from pathlib import Path
from mat_runtime.crew import CrewRegistry

registry = CrewRegistry(repo_root=Path("."))

# Discovery
print(registry.list_crews())              # ['dev-crew', 'review-crew']
print(registry.list_members("dev-crew"))  # ['coder', 'tester', 'reviewer']

# Runtime membership
registry.add_agent("dev-crew", "security")
registry.remove_agent("dev-crew", "tester")

# Persist changes (optional)
registry.save("dev-crew")

# Get a runnable Crew instance
crew = registry.get_crew("dev-crew")
```

## Validation

```bash
source .venv/bin/activate
python scripts/validate_crew.py
```

## See Also

- [Crew Schema Spec](../docs/superpowers/specs/2026-04-20-crew-schema-design.md)
- [MAT-42 Issue](https://github.com/zsleavitt/multi-agent-toolkit/issues/39)
- [MAT-43 Crew Runtime](https://github.com/zsleavitt/multi-agent-toolkit/issues/40)
- [MAT-44 Crew Composition (#41)](https://github.com/zsleavitt/multi-agent-toolkit/issues/41)
