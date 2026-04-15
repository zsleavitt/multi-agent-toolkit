# Multi-Agent Toolkit — Cursor Handoff

Read this file first when picking up work in **Cursor** (or any editor). It complements the root `README.md` and the Notion board.

## Quick summary

- **Claude Code** = orchestrator (plan, route, synthesize; no direct git/shell per architecture).
- **Codex** = implementation worker (scoped code, tests, refactors).
- **Gemini** (or equivalent) = git/CLI executor (allowlisted operations only).
- **MAT-1, MAT-2, MAT-3, MAT-4, MAT-6, MAT-8, MAT-9, MAT-10, MAT-11, MAT-12, MAT-14** are **Done** — schemas (including optional **`timeout_ms`** on MAT-1 / MAT-2 requests and MAT-12 **`git.add` / `git.commit` / `git.diff`** on MAT-1), ADR, CLAUDE.md, portable repo profile, orchestrator state document (including orchestrator session + fluency metadata), and Asana HITL trigger/callback contracts merged.
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
├── schemas/gemini-git-ops/v1/        # MAT-1 (+ MAT-11 timeout_ms, MAT-12 add/commit/diff ops)
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
| MAT-10 | Orchestrator sessions + fluency signals | **Done** |
| MAT-11 | Add timeout_ms to git-ops schema | **Done** |
| MAT-12 | Clarify git staging/commit scope | **Done** |
| MAT-13 | Add codex.diagnose/review ops (v1.1) | Backlog (P2) |
| MAT-14 | Add timeout_ms to MAT-2 schemas | **Done** |

## Key design decisions

1. **Git surface split (MAT-12)**: MAT-1 covers **branch / worktree / fetch / pull / push** and **`git add` / `git commit` / `git diff`** (allowlisted argv, no shell). **MAT-2** does not define those git wire ops — Codex stays scoped to implement/test/refactor; orchestrators route staging, commits, and repo diffs through MAT-1.

2. **Fluency (MAT-10)**: `claude-introspection` reads `~/.claude/`; high-signal planning/review should happen in the **main Claude Code** session when you care about scores. Optional MAT-4 fields **`orchestrator_session`** and checkpoint **`fluency`** (`schemas/orchestrator-state/v1/`, document `schema_version` **1.1.0**) record that linkage for tooling.

3. **Security**: Deny-by-default ops; **no shell** — fixed `git` argv only for the git bridge.

4. **Portability (MAT-9)**: `schemas/ai-team-repo-profile/v1/` — `ai-team.repo.json` / YAML profile decouples paths and ticket providers from hardcoded org defaults.

## Related codebases

- **Minions**: `~/Guideline/ai-tools/scripts/minions/` — Jira→PR pipeline; reference for stages, not a hard dependency.
- **Claude introspection**: `~/Gusto/claude-code/plugins/claude-introspection/` — fluency skill; see MAT-10.

## Suggested next steps (in order)

1. **Stay on `main`**, pull latest (see above).
2. **MAT-13** — Codex `codex.diagnose` / `codex.review` ops (v1.1 extension).
3. **MAT-5 / MAT-7** — Prototype and architecture audit when prioritized.

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
