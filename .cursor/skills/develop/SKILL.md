---
name: develop
description: Orchestrated development workflow — plans, implements, and coordinates the agent team. Use when implementing features, fixing bugs, or refactoring code that benefits from multi-agent coordination.
---

# Develop

Orchestrated development workflow — plans, implements, and coordinates the agent team.

## Usage

```
/develop <task description>
```

## Examples

- `/develop Add a fibonacci function to src/utils/math.py with input validation`
- `/develop Fix the null pointer exception in UserService.getProfile`
- `/develop Refactor the authentication module to use dependency injection`

## Instructions

1. Parse the task description from the input
2. Run the skill script:
   ```bash
   python lib/skills/develop/develop.py "<task>" --repo-root "$(pwd)"
   ```
3. Present the results: summary, files modified, follow-up recommendations

For complete documentation, see `lib/skills/develop/instructions.md`.
