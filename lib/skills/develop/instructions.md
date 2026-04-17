# Develop

Initiates an orchestrated development workflow. The orchestrator plans the task, routes work to specialized agents (coder, tester, reviewer), and synthesizes results.

## Usage

```
/develop <task description>
```

## Examples

### Implement a feature
```
/develop Add a fibonacci function to src/utils/math.py with input validation
```

### Fix a bug
```
/develop Fix the null pointer exception in UserService.getProfile when user not found
```

### Refactor code
```
/develop Refactor the authentication module to use dependency injection
```

### Add tests and implementation
```
/develop Implement a caching layer for the API with unit tests
```

## How it works

1. **Plan** — Orchestrator decomposes the task into work items
2. **Route** — Work items dispatched to appropriate agents:
   - `coder` — Implementation, refactoring, bug fixes
   - `tester` — Test writing and validation
   - `reviewer` — Code review (if needed)
3. **Coordinate** — Orchestrator manages dependencies between work items
4. **Synthesize** — Results combined into a summary

## When to use `/develop` vs single-agent skills

| Scenario | Use |
|----------|-----|
| New feature with tests | `/develop` (orchestrates coder + tester) |
| Bug fix that needs verification | `/develop` (coder + tester) |
| Just review an existing PR | `/review-pr` (reviewer only) |
| Just run/write tests | `/test` (tester only) |
| Security audit only | `/security-scan` (security only) |

## Error handling

| Error | Behavior |
|-------|----------|
| Task too vague | Orchestrator asks for clarification |
| Agent timeout | Returns partial results with status |
| Implementation fails | Reports failure, suggests next steps |

## Execution

When the user invokes this skill:

1. Parse the task description from the input after `/develop`

2. Construct a MAT-2 request with:
   - `op`: `codex.implement` (orchestrator will re-route as needed)
   - `instruction`: The task description
   - `repo_root`: Current working directory

3. Invoke the orchestrator agent:
   ```bash
   python -m mat_runtime invoke --agent orchestrator --instruction "<task>" --repo-root "$(pwd)"
   ```

4. The orchestrator will:
   - Decompose the task into work items
   - Route each item to the appropriate agent
   - Coordinate execution order based on dependencies
   - Return a synthesized summary

5. Present the results to the user:
   - Summary of completed work
   - Files modified (if any)
   - Any follow-up recommendations

## See also

- `/review-pr` — Direct reviewer invocation for PR review
- `/test` — Direct tester invocation for test writing/running
- `/diagnose` — Debug and investigate issues
- ADR 0003 — Skill naming conventions and fluency alignment
