---
name: invoke-agent
description: Invoke a MAT agent to perform a task (implement, test, review, etc.)
version: 1.0.0
---

# Invoke Agent

Delegates a task to a specialized MAT agent using the runtime adapter.

## Usage

```
/invoke-agent <agent> <task description>
```

## Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| `agent` | Yes | Agent name: `coder`, `tester`, `reviewer`, `security`, `researcher` |
| `task` | Yes | Task description / instruction for the agent |

## Examples

### Implement a feature
```
/invoke-agent coder Add a fibonacci function to src/utils/math.py
```

### Run tests
```
/invoke-agent tester Write unit tests for the new fibonacci function
```

### Code review
```
/invoke-agent reviewer Review the changes in src/utils/math.py for correctness and style
```

### Security analysis
```
/invoke-agent security Scan src/ for hardcoded credentials and SQL injection vulnerabilities
```

### Research
```
/invoke-agent researcher How does the authentication flow work in this codebase?
```

## Available Agents

| Agent | Role | Capabilities |
|-------|------|--------------|
| `coder` | worker | implement, refactor, diagnose |
| `tester` | worker | test, implement |
| `reviewer` | worker | review |
| `security` | worker | review, diagnose |
| `researcher` | executor | research, exploration |
| `orchestrator` | orchestrator | planning, routing |

## How it works

1. Parses the agent name and task from your input
2. Constructs a MAT-2 request with the task as `instruction`
3. Invokes `python -m mat_runtime invoke --agent <agent> --instruction "<task>"`
4. Returns the agent's response

## Error handling

- **Agent not found**: Check agent name spelling, run `python -m mat_runtime list-agents`
- **Operation not allowed**: The agent cannot perform this type of task
- **Timeout**: Task took too long, try breaking it into smaller pieces
- **CLI not found**: Install the required CLI tool (see `bin/setup`)

## Instructions

When the user invokes this skill:

1. Parse the input to extract:
   - `agent_name`: The first word after `/invoke-agent`
   - `task_description`: Everything after the agent name

2. Validate the agent name is one of: `coder`, `tester`, `reviewer`, `security`, `researcher`, `orchestrator`

3. Construct and run the command:
   ```bash
   python -m mat_runtime invoke --agent <agent_name> --instruction "<task_description>" --repo-root "$(pwd)"
   ```

4. Parse the JSON response:
   - If `ok: true`: Display the result to the user
   - If `ok: false`: Show the error message and suggest fixes

5. If the agent produces code changes, summarize what was modified.

## Notes

- The skill requires `mat_runtime` to be installed (`bin/setup`)
- Each agent uses its own CLI tool (claude, codex, gemini) per ADR 0002
- Tasks are scoped to the current repository (`repo_root`)
