---
name: diagnose
description: Debug and investigate issues — root cause analysis and fix suggestions. Use when tracking down bugs, analyzing failures, or understanding unexpected behavior.
---

# Diagnose

Debug and investigate issues — root cause analysis and fix suggestions.

## Usage

```
/diagnose <issue>
```

## Examples

- `/diagnose Why is UserService.getProfile throwing a null pointer exception?`
- `/diagnose The auth integration tests started failing after the last merge`
- `/diagnose Users report intermittent 500 errors on the checkout endpoint`

## Instructions

1. Parse the issue description from the input
2. Run the skill script:
   ```bash
   python lib/skills/diagnose/diagnose.py "<issue>" --repo-root "$(pwd)"
   ```
3. Present: root cause analysis, evidence with file locations, suggested fixes

For complete documentation, see `lib/skills/diagnose/instructions.md`.
