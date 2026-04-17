---
name: test
description: Write and run tests via the tester agent
version: 1.0.0
---

# Test

Invokes the tester agent to write tests, run test suites, and validate code behavior. Bypasses the orchestrator for focused testing tasks.

## Usage

```
/test <task>
```

## Examples

### Write unit tests
```
/test Write unit tests for src/utils/math.py covering edge cases
```

### Run existing tests
```
/test Run the test suite for the auth module and report failures
```

### Add test coverage
```
/test Add integration tests for the UserService API endpoints
```

### TDD workflow
```
/test Write failing tests for a fibonacci function that handles negative inputs
```

## Test types supported

| Type | Purpose | Scope |
|------|---------|-------|
| Unit | Test individual functions/methods | Single module |
| Integration | Test component interactions | Multiple modules |
| End-to-end | Test complete workflows | Full system |

## What the tester does

1. Understands what needs to be tested
2. Identifies test cases (happy path, edge cases, errors)
3. Writes tests following existing patterns
4. Runs tests and verifies results
5. Reports coverage and gaps

## When to use `/test` vs `/develop`

| Scenario | Use |
|----------|-----|
| Just write/run tests | `/test` |
| Implement feature + tests together | `/develop` |
| Debug test failures | `/diagnose` |

## Instructions

When the user invokes this skill:

1. Parse the testing task from the input after `/test`

2. Invoke the tester agent:
   ```bash
   python skills/test/test.py "<task>" --repo-root "$(pwd)"
   ```

3. Present the test results:
   - Tests added/modified
   - Pass/fail status
   - Coverage information (if available)

## See also

- `/develop` — Full orchestrated workflow with testing
- `/diagnose` — Debug failing tests
- ADR 0003 — Skill naming conventions
