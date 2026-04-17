---
name: test
description: Write and run tests via the tester agent. Use when writing unit tests, integration tests, or running test suites.
---

# Test

Write and run tests via the tester agent.

## Usage

```
/test <task>
```

## Examples

- `/test Write unit tests for src/utils/math.py covering edge cases`
- `/test Run the test suite for the auth module and report failures`
- `/test Add integration tests for the UserService API endpoints`

## Instructions

1. Parse the testing task from the input
2. Run the skill script:
   ```bash
   python lib/skills/test/test.py "<task>" --repo-root "$(pwd)"
   ```
3. Present: tests added/modified, pass/fail status, coverage information

For complete documentation, see `lib/skills/test/instructions.md`.
