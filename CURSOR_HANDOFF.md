# Multi-Agent Toolkit — Cursor Handoff

Read this file first when picking up work in **Cursor** (or any editor). It complements the root `README.md` and the Notion board.

## Quick summary

- **Claude Code** = orchestrator (plan, route, synthesize; no direct git/shell per architecture).
- **Codex** = implementation worker (scoped code, tests, refactors).
- **Gemini** (or equivalent) = git/CLI executor (allowlisted operations only).
- **MAT-1, MAT-2, MAT-3, MAT-4, MAT-6, MAT-8, MAT-9** are **Done** — schemas, ADR, CLAUDE.md, portable repo profile, orchestrator state document, and Asana HITL trigger/callback contracts merged.
- **14 tickets** live in Notion — [Multi-Agent Toolkit — Tickets](https://www.notion.so/c54de570f4ec433587b7cac957b950c1). Parent context: [Multi Agent Toolkit](https://www.notion.so/343ad673c6c280879a1de5fb5a9f9630).

## Sync the repo (do this first)

```bash
cd /Users/zach.leavitt/.claude/multi-agent-toolkit
git checkout main
git pull origin main
```

## Repository layout

```
multi-agent-toolkit/
├── CLAUDE.md                         # MAT-3: orchestrator context for Claude Code
├── CURSOR_HANDOFF.md                 # This file
├── docs/adr/                         # MAT-8 and later ADRs
├── config/schema-registry.json       # Bundle paths; optional published_document_base
├── schemas/gemini-git-ops/v1/        # MAT-1: git ops schemas (merged)
│   ├── manifest.json
│   ├── request.schema.json
│   ├── response.schema.json
│   └── examples/
├── schemas/codex-code-exec/v1/       # MAT-2: Codex code-exec schemas
│   ├── manifest.json
│   ├── request.schema.json
│   ├── response.schema.json
│   └── examples/
├── schemas/ai-team-repo-profile/v1/  # MAT-9: ai-team.repo profile + work-item adapter
│   ├── manifest.json
│   ├── repo-profile.schema.json
│   └── examples/
├── schemas/orchestrator-state/v1/      # MAT-4: queue, artifacts, checkpoints
│   ├── manifest.json
│   ├── orchestrator-state.schema.json
│   └── examples/
├── schemas/hitl-asana-approval/v1/   # MAT-6: Asana HITL trigger + callback
│   ├── manifest.json
│   ├── trigger.schema.json
│   ├── callback.schema.json
│   └── examples/
├── scripts/validate_gemini_git_ops.py
├── scripts/validate_codex_code_exec.py
├── scripts/validate_ai_team_repo_profile.py
├── scripts/validate_orchestrator_state.py
├── scripts/validate_hitl_asana_approval.py
├── research/multi-agent-research.md  # Architecture research
└── requirements-dev.txt
```

## MAT-1 status (merged)

**PR #1** landed on `main`: JSON Schemas for Claude → executor git/CLI requests/responses, deny-by-default `manifest.json` allowlist, `config/schema-registry.json`, validation script, and example payloads.

## Ticket board (Notion)

| Ticket | Name | Status |
|--------|------|--------|
| MAT-1 | Claude → Gemini git/CLI contracts | **Done** |
| MAT-2 | Claude → Codex code execution contracts | **Done** |
| MAT-3 | CLAUDE.md / repo context package | **Done** |
| MAT-4 | State: queue, artifacts, checkpoints | **Done** |
| MAT-5 | Gumloop workflow prototype | Backlog (P2) |
| MAT-6 | HITL: Asana approval triggers | **Done** |
| MAT-7 | Audit repo vs architecture checklist | Backlog (P2) |
| MAT-8 | ADR: Claude Code vs Cursor orchestrator | **Done** |
| MAT-9 | Portable repo profile + work-item adapter | **Done** |
| MAT-10 | Orchestrator sessions + fluency signals | Backlog (P1) |
| MAT-11 | Add timeout_ms to git-ops schema | Backlog (P2) |
| MAT-12 | Clarify git staging/commit scope | Backlog (P2) |
| MAT-13 | Add codex.diagnose/review ops (v1.1) | Backlog (P2) |
| MAT-14 | Add timeout_ms to MAT-2 schemas | Backlog (P2) |

## Key design decisions

1. **Git surface split**: MAT-1 covers **branch / worktree / fetch / pull / push** style ops. Whether **`git add` / `git commit` / `git diff`** live under MAT-1 (executor), MAT-2 (Codex in a sandbox), or both is **explicitly deferred** — track in **MAT-12** so MAT-2 stays “code execution” scoped.

2. **Fluency (MAT-10)**: `claude-introspection` reads `~/.claude/`; high-signal planning/review should happen in the **main Claude Code** session when you care about scores.

3. **Security**: Deny-by-default ops; **no shell** — fixed `git` argv only for the git bridge.

4. **Portability (MAT-9)**: `schemas/ai-team-repo-profile/v1/` — `ai-team.repo.json` / YAML profile decouples paths and ticket providers from hardcoded org defaults.

## Related codebases

- **Minions**: `~/Guideline/ai-tools/scripts/minions/` — Jira→PR pipeline; reference for stages, not a hard dependency.
- **Claude introspection**: `~/Gusto/claude-code/plugins/claude-introspection/` — fluency skill; see MAT-10.

## Suggested next steps (in order)

1. **Stay on `main`**, pull latest (see above).
2. **MAT-10** — Orchestrator sessions + fluency signals (next P1 on the board).
3. **MAT-11 / MAT-12 / MAT-13 / MAT-14** — Schema follow-ups (`timeout_ms`, git staging/commit scope vs MAT-2, Codex ops, and related).

## Validation

```bash
cd /Users/zach.leavitt/.claude/multi-agent-toolkit
python3 -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
python scripts/validate_gemini_git_ops.py
python scripts/validate_codex_code_exec.py
python scripts/validate_ai_team_repo_profile.py
python scripts/validate_orchestrator_state.py
python scripts/validate_hitl_asana_approval.py
```

Optional: `export MAT_GEMINI_GIT_OPS_V1=/path/to/schemas/gemini-git-ops/v1`, `export MAT_CODEX_CODE_EXEC_V1=/path/to/schemas/codex-code-exec/v1`, `export MAT_AI_TEAM_REPO_PROFILE_V1=/path/to/schemas/ai-team-repo-profile/v1`, `export MAT_ORCHESTRATOR_STATE_V1=/path/to/schemas/orchestrator-state/v1`, or `export MAT_HITL_ASANA_APPROVAL_V1=/path/to/schemas/hitl-asana-approval/v1` if a bundle is not at the default `root_relative` path.

## References

- Notion tickets: https://www.notion.so/c54de570f4ec433587b7cac957b950c1  
- Notion parent hub: https://www.notion.so/343ad673c6c280879a1de5fb5a9f9630  
- Merged PRs: [#1](https://github.com/zsleavitt/multi-agent-toolkit/pull/1), [#2](https://github.com/zsleavitt/multi-agent-toolkit/pull/2)  
- Research: `research/multi-agent-research.md`
