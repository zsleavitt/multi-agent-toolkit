---
name: review-pr
description: Code review for pull requests — quality, security, and correctness analysis. Use when reviewing PRs, staged changes, or specific files.
version: 1.0.0
allowed-tools: Bash(python *)
---

# Review PR

Invokes the reviewer agent to analyze code for quality, security, and correctness.

For complete documentation, see [instructions.md](../../../lib/skills/review-pr/instructions.md).

## Quick Start

```
/review-pr <target>
```

## Examples

- `/review-pr Review the staged changes for security issues`
- `/review-pr Review src/auth/login.py for OWASP vulnerabilities`
- `/review-pr Review PR #42 focusing on error handling`

## Execution

Run the skill script:

```bash
python lib/skills/review-pr/review_pr.py "$ARGUMENTS" --repo-root "$(pwd)"
```

Returns findings organized by severity: blocker, issue, suggestion, info.
