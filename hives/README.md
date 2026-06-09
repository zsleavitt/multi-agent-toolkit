# Hives

This directory contains Hive definitions — JSON files that define top-level orchestrators managing multiple named Crews with inter-crew routing and global resource limits.

## File Format

Each hive is a JSON file following the schema at `schemas/hive/v1/hive.schema.json`. The filename must match the `name` field (e.g. `dev-pipeline.json` → `"name": "dev-pipeline"`).

## Hive Definitions

| File | Purpose |
|------|---------|
| `dev-pipeline.json` | Sequential dev → review pipeline using `dev-crew` and `review-crew` |

## Composition Patterns

### Dev pipeline

- **dev-pipeline** (`dev-pipeline.json`): Run implementation with `dev-crew`, then hand off to `review-crew` on success. Uses `depends_on` for sequencing and explicit routing rules.

### Crew references

Each crew entry requires a `ref` matching a file in `crews/`:

```json
"crews": [
  { "ref": "dev-crew" },
  {
    "ref": "review-crew",
    "depends_on": ["dev-crew"],
    "role": "review"
  }
]
```

### Inter-crew routing strategies

| Strategy | When to use |
|----------|-------------|
| `sequential` | Process crews in order, respecting `depends_on` |
| `capability` | Route by crew `role` label (runtime) |
| `dependency` | Follow `depends_on` graph only |
| `manual` | Explicit `rules` only (requires rules array) |

## Validation

```bash
source .venv/bin/activate
python scripts/validate_hive.py
```

## See Also

- [Hive Schema Spec](../docs/superpowers/specs/2026-04-21-hive-schema-design.md)
- [MAT-49 Issue](https://github.com/zsleavitt/multi-agent-toolkit/issues/46)
- [MAT-50 Hive Runtime](https://github.com/zsleavitt/multi-agent-toolkit/issues/47)
