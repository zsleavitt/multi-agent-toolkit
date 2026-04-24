---
name: finish-branch
description: Close work items when branch is merged
version: 1.0.0
allowed-tools:
  - Bash
  - Read
  - Grep
---

# /finish-branch

Closes work items when a development branch is merged. Extracts MAT-XX from branch name, looks up the corresponding issue, and closes it.

## Quick Start

```
/finish-branch                              # Close for current branch
/finish-branch --branch feat/mat-42-test    # Specify branch
/finish-branch --comment "Merged in PR #100" # Add comment
/finish-branch --dry-run                    # Preview only
```

## Full Documentation

See: `lib/skills/finish_branch/instructions.md`

## Execution

When invoked, run:

```bash
python lib/skills/finish_branch/finish_branch.py [args]
```

Parse the JSON output and report the result to the user.
