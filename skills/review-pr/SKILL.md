---
name: review-pr
description: Code review for pull requests — quality, security, and correctness analysis
version: 1.0.0
---

# Review PR

Invokes the reviewer agent to analyze code for quality, security, and correctness. Bypasses the orchestrator for focused, single-agent review.

## Usage

```
/review-pr <target>
```

## Examples

### Review current changes
```
/review-pr Review the staged changes for security issues
```

### Review a specific file
```
/review-pr Review src/auth/login.py for OWASP vulnerabilities
```

### Review a PR by number
```
/review-pr Review PR #42 focusing on error handling
```

### Full code review
```
/review-pr Comprehensive review of the changes in src/api/
```

## What the reviewer checks

| Category | Checks |
|----------|--------|
| **Correctness** | Logic errors, edge cases, bugs |
| **Security** | SQL injection, XSS, hardcoded secrets, auth issues |
| **Quality** | Naming, structure, complexity, style consistency |
| **Maintainability** | Readability, modularity, documentation |

## Severity levels

- **blocker** — Must fix before merge (security flaw, data loss risk)
- **issue** — Should fix (bug, significant quality problem)
- **suggestion** — Consider fixing (improvement opportunity)
- **info** — FYI, optional (style preference)

## When to use `/review-pr` vs `/develop`

| Scenario | Use |
|----------|-----|
| Review existing code/PR | `/review-pr` |
| Implement + review in one workflow | `/develop` |
| Security-focused audit | `/security-scan` |

## Instructions

When the user invokes this skill:

1. Parse the review target from the input after `/review-pr`

2. Invoke the reviewer agent:
   ```bash
   python skills/review-pr/review_pr.py "<target>" --repo-root "$(pwd)"
   ```

3. Present the review findings organized by severity

## See also

- `/develop` — Full orchestrated workflow
- `/security-scan` — Security-focused analysis
- ADR 0003 — Skill naming conventions
