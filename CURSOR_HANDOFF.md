# Multi-Agent Toolkit — Cursor Handoff

Read this file first when picking up work in **Cursor** (or any editor). It complements the root `README.md` and the Notion board.

## Quick summary

- **Claude Code** = orchestrator (plan, route, synthesize; no direct git/shell per architecture).
- **Codex** = implementation worker (scoped code, tests, refactors).
- **Gemini** (or equivalent) = git/CLI executor (allowlisted operations only).
- **MAT-1** JSON Schemas for git ops are **merged to `main`** ([PR #1](https://github.com/zsleavitt/multi-agent-toolkit/pull/1)).
- **12 tickets** live in Notion — [Multi-Agent Toolkit — Tickets](https://www.notion.so/c54de570f4ec433587b7cac957b950c1). Parent context: [Multi Agent Toolkit](https://www.notion.so/343ad673c6c280879a1de5fb5a9f9630).

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
├── scripts/validate_gemini_git_ops.py
├── scripts/validate_codex_code_exec.py
├── research/multi-agent-research.md  # Architecture research
└── requirements-dev.txt
```

## MAT-1 status (merged)

**PR #1** landed on `main`: JSON Schemas for Claude → executor git/CLI requests/responses, deny-by-default `manifest.json` allowlist, `config/schema-registry.json`, validation script, and example payloads.

## Ticket board (Notion)

| Ticket | Name | Typical next |
|--------|------|----------------|
| MAT-1 | Claude → Gemini git/CLI contracts | **Done** (merged); follow-ups → MAT-11 / MAT-12 |
| MAT-2 | Claude → Codex **code execution** contracts | **In repo** — `schemas/codex-code-exec/v1/` + `scripts/validate_codex_code_exec.py` (not repo-wide git; see MAT-12) |
| MAT-3 | CLAUDE.md / repo context package | **In repo** — root `CLAUDE.md` (extend per app repo as needed) |
| MAT-4 | State: queue, artifacts, checkpoints | P1 |
| MAT-5 | Gumloop workflow prototype | P2 |
| MAT-6 | HITL: Asana approval triggers | P1 |
| MAT-7 | Audit repo vs architecture checklist | P2 |
| MAT-8 | ADR: Claude Code vs Cursor orchestrator | **In repo** — `docs/adr/0001-primary-orchestrator-claude-code-vs-cursor.md` |
| MAT-9 | Portable repo profile + work-item adapter | P0 |
| MAT-10 | Orchestrator sessions + fluency signals | P1 |
| MAT-11 | Add `timeout_ms` (and similar) to git-ops schema | P2 |
| MAT-12 | Clarify git staging/commit scope vs MAT-2 | P2 |

## Key design decisions

1. **Git surface split**: MAT-1 covers **branch / worktree / fetch / pull / push** style ops. Whether **`git add` / `git commit` / `git diff`** live under MAT-1 (executor), MAT-2 (Codex in a sandbox), or both is **explicitly deferred** — track in **MAT-12** so MAT-2 stays “code execution” scoped.

2. **Fluency (MAT-10)**: `claude-introspection` reads `~/.claude/`; high-signal planning/review should happen in the **main Claude Code** session when you care about scores.

3. **Security**: Deny-by-default ops; **no shell** — fixed `git` argv only for the git bridge.

4. **Portability (MAT-9)**: Repo profile schema decouples paths and ticket providers from hardcoded org defaults.

## Related codebases

- **Minions**: `~/Guideline/ai-tools/scripts/minions/` — Jira→PR pipeline; reference for stages, not a hard dependency.
- **Claude introspection**: `~/Gusto/claude-code/plugins/claude-introspection/` — fluency skill; see MAT-10.

## Suggested next steps (in order)

1. **Stay on `main`**, pull latest (see above).
2. **MAT-9** — Portable repo profile + work-item adapter (P0 on the board).
3. **MAT-4** — State: queue, artifacts, checkpoints.
4. **MAT-11 / MAT-12** — Schema follow-ups (`timeout_ms`; git staging/commit scope vs MAT-2).

## Validation

```bash
cd /Users/zach.leavitt/.claude/multi-agent-toolkit
python3 -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
python scripts/validate_gemini_git_ops.py
python scripts/validate_codex_code_exec.py
```

Optional: `export MAT_GEMINI_GIT_OPS_V1=/path/to/schemas/gemini-git-ops/v1` or `export MAT_CODEX_CODE_EXEC_V1=/path/to/schemas/codex-code-exec/v1` if a bundle is not at the default `root_relative` path.

## References

- Notion tickets: https://www.notion.so/c54de570f4ec433587b7cac957b950c1  
- Notion parent hub: https://www.notion.so/343ad673c6c280879a1de5fb5a9f9630  
- Merged PR: https://github.com/zsleavitt/multi-agent-toolkit/pull/1  
- Research: `research/multi-agent-research.md`
