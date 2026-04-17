---
name: review-pr
description: Code review for pull requests — quality, security, and correctness analysis. Use when reviewing staged changes, specific files, or pull requests.
---

# Review PR

Code review for pull requests — quality, security, and correctness analysis.

## Usage

```
/review-pr <target>
```

## Examples

- `/review-pr Review the staged changes for security issues`
- `/review-pr Review src/auth/login.py for OWASP vulnerabilities`
- `/review-pr Review PR #42 focusing on error handling`

## Instructions

1. Parse the review target from the input
2. Run the skill script:
   ```bash
   python lib/skills/review-pr/review_pr.py "<target>" --repo-root "$(pwd)"
   ```
3. Present findings organized by severity: blocker, issue, suggestion, info

For complete documentation, see `lib/skills/review-pr/instructions.md`.
