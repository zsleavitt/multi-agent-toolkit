# Crews

This directory contains Crew definitions — JSON files that define named collections of agents with shared goals and routing configuration.

## File Format

Each crew is a JSON file following the schema at `schemas/crew/v1/crew.schema.json`.

## Example

```json
{
  "schema_version": "1.0.0",
  "name": "dev-crew",
  "description": "Development team",
  "shared_goal": "Implement features with high quality",
  "agents": ["coder", "tester", "reviewer"],
  "routing": {
    "strategy": "capability",
    "match_on": ["tags", "languages"]
  }
}
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
