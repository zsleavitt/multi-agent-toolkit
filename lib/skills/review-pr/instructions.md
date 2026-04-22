# Review PR

Invokes the reviewer agent to analyze code for quality, security, and correctness. Bypasses the orchestrator for focused, single-agent review.

## Usage

```
/review-pr <target> [--swarm] [--post] [--min-severity info|suggestion|issue|blocker]
```

### Options

| Flag | Description |
|------|-------------|
| `--swarm` | Multi-model review (Claude + Codex + Gemini) with consolidated output. **Auto-posts to GitHub** when target is a PR URL. |
| `--post`, `-p` | Post findings as GitHub PR review (single-model path only) |
| `--min-severity`, `-m` | Minimum severity to post (default: `info`) |

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

### Post review to GitHub PR
```
/review-pr Review staged changes --post
```

### Post only issues and blockers
```
/review-pr Review src/api/ --post --min-severity issue
```

### Multi-model review (auto-posts to PR)
```
/review-pr https://github.com/owner/repo/pull/123 --swarm
```

## Multi-Model Review (`--swarm`)

When `--swarm` is passed with a GitHub PR URL:

1. **Pre-fetches** the PR diff and metadata via `gh` CLI
2. **Dispatches** the same diff to Claude, Codex, and Gemini in parallel
3. **Consolidates** findings into a single ranked review (Claude synthesizes)
4. **Posts** the consolidated review as a PR comment automatically
5. **Prints** the review locally so you see what was posted

The comment header shows which models contributed:
- All succeed: "Reviewed by Claude, Codex, and Gemini in parallel"
- Partial: "Reviewed by Claude and Codex (Gemini unavailable)"

**Requirements:**
- GitHub CLI (`gh`) installed and authenticated
- Claude, Codex, and Gemini CLIs configured

**Note:** Large diffs (>50k chars) are truncated to stay within model context limits.

## GitHub Integration

When using `--post`, the skill will:
1. Check that `gh` CLI is installed and authenticated
2. Detect if there's an open PR for the current branch
3. Post inline comments for each finding
4. Submit a review with appropriate status (REQUEST_CHANGES if blockers/issues, COMMENT otherwise)

**Requirements:**
- GitHub CLI (`gh`) installed and authenticated (`gh auth login`)
- Current branch must have an open PR (or you'll be prompted to create one)

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

## Execution

When the user invokes this skill:

1. Parse the review target from the input after `/review-pr`

2. Invoke the reviewer agent (use `python3` on systems without a `python` shim; or activate `.venv` first so `python` works):
   ```bash
   python3 lib/skills/review-pr/review_pr.py "<target>" --repo-root "$(pwd)"
   ```

3. Present the review findings organized by severity

## See also

- `/develop` — Full orchestrated workflow
- `/security-scan` — Security-focused analysis
- ADR 0003 — Skill naming conventions
