# Develop

Runs the **coder** agent (OpenAI **Codex** by default) with MAT-2 **`codex.implement`** on your task. This is the default path for **implementation** from `/develop` in Claude Code, Cursor, or any surface that executes the skill script.

For **planning only** (no code changes), use **`/plan`**. For **code review** with **Claude Code** by default in this repository, use **`/review-pr`** (reviewer agent).

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

## How it works

1. The skill builds a **MAT-2** request (`op`: `codex.implement`, your instruction, `repo_root`).
2. **`AgentRouter`** invokes the **`coder`** agent → **`CodexAdapter`** → `codex exec` (see ADR 0002, `agents/coder.md`).
3. Output is formatted for the chat session.

This is a **single-agent** implementation pass, not an in-process multi-agent loop. Chain **`/plan`** → **`/develop`** → **`/review-pr`** yourself when you want that sequence.

## Personalizing CLIs (MAT-16)

Copy **`mat-config.example.json`** to **`mat-config.json`** (or **`.mat/config.json`**) in the repo root. The router merges **`agents.<role>`** then **`agents.<agent-name>`**, so you can override only **`reviewer`** (e.g. switch review back to **`codex-review`**) without changing **`coder`**.

## Execution

When the user invokes this skill:

1. Parse the task description from the input after `/develop`.
2. Run:

   ```bash
   python lib/skills/develop/develop.py "$ARGUMENTS" --repo-root "$(pwd)"
   ```

3. Present the Codex result: summary, suggested follow-ups, and any errors.
