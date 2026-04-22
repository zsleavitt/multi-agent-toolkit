# Swarms

This directory contains Swarm definitions — JSON files that define parallel dispatch to multiple candidates with consensus strategies.

## File Format

Each swarm is a JSON file following the schema at `schemas/swarm/v1/swarm.schema.json`.

## Example

```json
{
  "schema_version": "1.0.0",
  "name": "model-comparison",
  "description": "Compare multiple models on implementation tasks",
  "dispatch_mode": "parallel_model",
  "candidates": ["claude", "codex", "gemini"],
  "consensus_strategy": "majority-vote"
}
```

## Dispatch Modes

- **parallel_model**: Send same task to multiple CLI adapters (claude, codex, gemini)
- **variant**: Send same task to multiple agent variants (python-engineer, ruby-engineer)

## Consensus Strategies

| Strategy | Valid Modes | Behavior |
|----------|-------------|----------|
| `first-complete` | parallel_model | Return first successful response |
| `majority-vote` | parallel_model | Return most common result (requires ≥3 candidates) |
| `return-all` | variant | Return array of all responses |

## Validation

```bash
source .venv/bin/activate
python scripts/validate_swarm.py
```

## See Also

- [Swarm Schema Spec](../docs/superpowers/specs/2026-04-21-swarm-schema-design.md)
- [MAT-45 Issue](https://github.com/zsleavitt/multi-agent-toolkit/issues/42)
