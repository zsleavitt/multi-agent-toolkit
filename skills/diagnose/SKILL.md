---
name: diagnose
description: Debug and investigate issues — root cause analysis and fix suggestions
version: 1.0.0
---

# Diagnose

Invokes agents to debug issues, investigate errors, and perform root cause analysis. Uses the coder agent's diagnose capability for code-level debugging.

## Usage

```
/diagnose <issue>
```

## Examples

### Debug an error
```
/diagnose Why is UserService.getProfile throwing a null pointer exception?
```

### Investigate test failure
```
/diagnose The auth integration tests started failing after the last merge
```

### Performance issue
```
/diagnose The API response time doubled after deploying v2.3
```

### Trace a bug
```
/diagnose Users report intermittent 500 errors on the checkout endpoint
```

## What diagnose does

1. Analyzes the issue description
2. Explores relevant code paths
3. Identifies potential root causes
4. Suggests fixes with specific locations
5. Recommends verification steps

## Diagnosis output

```
## Diagnosis: [Issue Summary]

### Root Cause
[Explanation of what's causing the issue]

### Evidence
- File: `path/to/file.py:42`
- Observation: [What was found]

### Suggested Fix
[Specific changes to make]

### Verification
[How to confirm the fix works]
```

## When to use `/diagnose` vs other skills

| Scenario | Use |
|----------|-----|
| Debug an error or bug | `/diagnose` |
| Fix the bug after diagnosis | `/develop` |
| Failing tests | `/diagnose` then `/test` |
| Security vulnerability | `/security-scan` |

## Instructions

When the user invokes this skill:

1. Parse the issue description from the input after `/diagnose`

2. Invoke the coder agent with diagnose op:
   ```bash
   python skills/diagnose/diagnose.py "<issue>" --repo-root "$(pwd)"
   ```

3. Present the diagnosis:
   - Root cause analysis
   - Evidence with file locations
   - Suggested fixes
   - Verification steps

## See also

- `/develop` — Implement fixes after diagnosis
- `/test` — Verify fixes with tests
- ADR 0003 — Skill naming conventions
