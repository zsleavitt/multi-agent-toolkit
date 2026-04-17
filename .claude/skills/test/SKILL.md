---
name: test
description: Write and run tests via the tester agent. Use when writing unit tests, running test suites, or adding test coverage.
version: 1.0.0
allowed-tools: Bash(python *)
---

# Test

Invokes the tester agent to write tests, run test suites, and validate code behavior.

For complete documentation, see [instructions.md](../../../lib/skills/test/instructions.md).

## Quick Start

```
/test <task>
```

## Examples

- `/test Write unit tests for src/utils/math.py covering edge cases`
- `/test Run the test suite for the auth module and report failures`
- `/test Add integration tests for the UserService API endpoints`

## Execution

Run the skill script:

```bash
python lib/skills/test/test.py "$ARGUMENTS" --repo-root "$(pwd)"
```

Returns test results including pass/fail status and coverage information.
