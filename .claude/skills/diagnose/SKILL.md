---
name: diagnose
description: Debug and investigate issues — root cause analysis and fix suggestions. Use when debugging errors, investigating test failures, or tracing bugs.
version: 1.0.0
allowed-tools: Bash(python *)
---

# Diagnose

Invokes agents to debug issues, investigate errors, and perform root cause analysis.

For complete documentation, see [instructions.md](../../../lib/skills/diagnose/instructions.md).

## Quick Start

```
/diagnose <issue>
```

## Examples

- `/diagnose Why is UserService.getProfile throwing a null pointer exception?`
- `/diagnose The auth integration tests started failing after the last merge`
- `/diagnose Users report intermittent 500 errors on the checkout endpoint`

## Execution

Run the skill script:

```bash
python lib/skills/diagnose/diagnose.py "$ARGUMENTS" --repo-root "$(pwd)"
```

Returns root cause analysis, evidence with file locations, and suggested fixes.
