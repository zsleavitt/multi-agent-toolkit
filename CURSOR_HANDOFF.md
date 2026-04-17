# Multi-Agent Toolkit — Cursor Handoff

Read this file first when picking up work in **Cursor** (or any editor). It complements the root `README.md` and the Notion board.

## Quick summary

- **Claude Code** = orchestrator (plan, route, synthesize; no direct git/shell per architecture).
- **Codex** = code worker (implement, test, refactor, diagnose, review; optional **`timeout_ms`**).
- **Gemini** (or equivalent) = git/CLI executor (allowlisted operations only).
- **22 schema-track tickets are Done** on `main` — MAT-1 through MAT-14, MAT-16–19, MAT-22, MAT-23, MAT-25, MAT-26 merged. **MAT-5 (Gumloop prototype)** is merged. **Remaining backlog:** MAT-7, MAT-20–21, MAT-24.
- **Wire formats in this repo (complete):**
  - **MAT-1** — Git executor: fetch / pull / push / branch / worktree + **`git.add`** / **`git.commit`** / **`git.diff`**; optional **`timeout_ms`** (MAT-11).
  - **MAT-2** — Code worker: **`codex.implement`** / **`codex.test`** / **`codex.refactor`** / **`codex.diagnose`** / **`codex.review`**; optional **`timeout_ms`** (MAT-14); MAT-13 uses **`schema_version`** **1.2.0** for diagnose/review.
  - **MAT-4** — Orchestrator state: queue, artifacts, checkpoints; optional orchestrator session + **fluency** (MAT-10) on `schema_version` **1.1.0** documents.
  - **MAT-6** — HITL: Asana approval **trigger** and **callback** JSON.
  - **MAT-9** — Portable **`ai-team.repo`** profile + work-item adapters (Linear, Jira, GitHub Issues, file, none).
  - **MAT-16** — Agent configuration: CLI-based agent bindings (which CLI tool handles which role). No API keys required.
  - **MAT-17** — Agent definitions: Markdown files with YAML frontmatter defining agent identity, capabilities, and system prompts.
- **Tickets** live in Notion (set `$MAT_NOTION_TICKETS_URL` and `$MAT_NOTION_HUB_URL` in your environment).

## Sync the repo (do this first)

```bash
cd /path/to/multi-agent-toolkit
git checkout main
git pull origin main
```

## Repository layout

```
multi-agent-toolkit/
├── bin/setup                         # MAT-26: Setup script (venv, deps, CLI check)
├── CLAUDE.md                         # MAT-3: orchestrator context for Claude Code
├── CURSOR_HANDOFF.md                 # This file
├── docs/adr/                         # MAT-8 and later ADRs
├── config/schema-registry.json       # Bundle paths; optional published_document_base
├── schemas/gemini-git-ops/v1/        # MAT-1 (+ MAT-11 timeout_ms, MAT-12 add/commit/diff ops)
│   ├── manifest.json
│   ├── request.schema.json
│   ├── response.schema.json
│   └── examples/
├── schemas/codex-code-exec/v1/       # MAT-2 (+ MAT-13 diagnose/review, MAT-14 timeout_ms)
│   ├── manifest.json
│   ├── request.schema.json
│   ├── response.schema.json
│   └── examples/
├── schemas/ai-team-repo-profile/v1/  # MAT-9: ai-team.repo profile + work-item adapter
│   ├── manifest.json
│   ├── repo-profile.schema.json
│   └── examples/
├── schemas/orchestrator-state/v1/      # MAT-4 (+ MAT-10 fluency / session fields)
│   ├── manifest.json
│   ├── orchestrator-state.schema.json
│   └── examples/
├── schemas/hitl-asana-approval/v1/   # MAT-6: Asana HITL trigger + callback
│   ├── manifest.json
│   ├── trigger.schema.json
│   ├── callback.schema.json
│   └── examples/
├── schemas/provider-config/v1/       # MAT-16: LLM provider configuration
│   ├── manifest.json
│   ├── provider-config.schema.json
│   └── examples/
├── schemas/agent-definition/v1/      # MAT-17: Agent definition format
│   ├── manifest.json
│   ├── agent-frontmatter.schema.json
│   └── examples/
├── agents/                           # MAT-17: Core agent definitions
│   ├── orchestrator.md
│   ├── coder.md
│   ├── researcher.md
│   ├── reviewer.md
│   ├── security.md
│   └── tester.md
├── mat_runtime/                      # MAT-18: Runtime adapter layer
│   ├── __init__.py
│   ├── __main__.py                   # CLI: python -m mat_runtime
│   ├── router.py                     # AgentRouter class
│   ├── config.py                     # Config loading
│   ├── adapters/                     # CLI tool adapters
│   └── tests/
├── skills/
│   ├── lib/                          # Shared skill utilities
│   │   └── formatting.py             # Response formatting
│   ├── develop/                      # MAT-19: /develop — orchestrated workflow
│   ├── review-pr/                    # MAT-27: /review-pr — code review
│   ├── test/                         # MAT-28: /test — testing
│   ├── diagnose/                     # MAT-29: /diagnose — debugging
│   └── plan/                         # MAT-30: /plan — planning only
├── scripts/validate_gemini_git_ops.py
├── scripts/validate_codex_code_exec.py
├── scripts/validate_ai_team_repo_profile.py
├── scripts/validate_orchestrator_state.py
├── scripts/validate_hitl_asana_approval.py
├── scripts/validate_gumloop_examples.py  # MAT-5: examples/gumloop + embedded MAT-2
├── scripts/validate_provider_config.py   # MAT-16: provider configuration
├── scripts/validate_agent_definitions.py # MAT-17: agent definitions + frontmatter
├── scripts/gumloop_start_pipeline.py     # MAT-5: optional start_pipeline POST
├── docs/prototypes/                  # MAT-5: Gumloop handoff (non-schema)
├── examples/gumloop/                 # MAT-5: Gumloop API / input conventions
├── research/multi-agent-research.md  # Architecture research
└── requirements-dev.txt
```

## Schema status (merged on `main`)

MAT-1 through MAT-17 (plus MAT-22, MAT-23) are represented in `schemas/*/v1/` with `manifest.json` allowlists (where applicable), `examples/`, and **eight** `scripts/validate_*.py` bundle validators. Historical bootstrap: **PR #1** (MAT-1 git contracts + registry + validators).

## Ticket board (Notion)

| Ticket | Name | Status |
|--------|------|--------|
| MAT-1 | Claude → Gemini git/CLI contracts | **Done** |
| MAT-2 | Claude → Codex code execution contracts | **Done** |
| MAT-3 | CLAUDE.md / repo context package | **Done** |
| MAT-4 | State: queue, artifacts, checkpoints | **Done** |
| MAT-5 | Gumloop workflow prototype | **Done** |
| MAT-6 | HITL: Asana approval triggers | **Done** |
| MAT-7 | Audit repo vs architecture checklist | Backlog (P2) |
| MAT-8 | ADR: Claude Code vs Cursor orchestrator | **Done** |
| MAT-9 | Portable repo profile + work-item adapter | **Done** |
| MAT-10 | Orchestrator sessions + fluency signals | **Done** |
| MAT-11 | Add timeout_ms to git-ops schema | **Done** |
| MAT-12 | Clarify git staging/commit scope | **Done** |
| MAT-13 | Add codex.diagnose/review ops (v1.1) | **Done** |
| MAT-14 | Add timeout_ms to MAT-2 schemas | **Done** |
| MAT-16 | Provider configuration schema | **Done** |
| MAT-17 | Agent definition format | **Done** |
| MAT-18 | Runtime adapter layer | **Done** |
| MAT-19 | Orchestrator skill integration | **Done** |
| MAT-20 | Consumer repo documentation | Backlog (P1) |
| MAT-21 | Optional LangChain integration | Backlog (P2) |
| MAT-22 | Security: .gitignore + deps | **Done** |
| MAT-23 | Schema: repo_root validation | **Done** |
| MAT-24 | Schema: maxLength on instructions | Backlog (P2) |
| MAT-25 | Security agent definition | **Done** |
| MAT-26 | Setup script + CLI prerequisites | **Done** |
| MAT-27 | Skill: /review-pr | **Done** |
| MAT-28 | Skill: /test | **Done** |
| MAT-29 | Skill: /diagnose | **Done** |
| MAT-30 | Skill: /plan | **Done** |
| MAT-31 | /review-pr: post comments to PR | Backlog (P2) |
| MAT-32 | Schema: notion work_item_source adapter | **Done** |
| MAT-33 | Runtime: work item adapter classes | **Done** |
| MAT-34 | Skill: /ticket (orchestrator-level) | **Done** |
| MAT-35 | Setup wizard: MCP + ticket config | Backlog (P2) |

## Key design decisions

1. **Git surface split (MAT-12)**: MAT-1 covers **branch / worktree / fetch / pull / push** and **`git add` / `git commit` / `git diff`** (allowlisted argv, no shell). **MAT-2** does not define those git wire ops — Codex stays scoped to **implement / test / refactor / diagnose / review**; orchestrators route staging, commits, and repo diffs through MAT-1.

2. **Fluency (MAT-10)**: `claude-introspection` reads `~/.claude/`; high-signal planning/review should happen in the **main Claude Code** session when you care about scores. Optional MAT-4 fields **`orchestrator_session`** and checkpoint **`fluency`** (`schemas/orchestrator-state/v1/`, document `schema_version` **1.1.0**) record that linkage for tooling.

3. **Security**: Deny-by-default ops; **no shell** — fixed `git` argv only for the git bridge.

4. **Portability (MAT-9)**: `schemas/ai-team-repo-profile/v1/` — `ai-team.repo.json` / YAML profile decouples paths and ticket providers from hardcoded org defaults.

5. **Diagnose / review (MAT-13)**: **`codex.diagnose`** and **`codex.review`** are MAT-2 ops with structured response `$defs` (`result_diagnose`, `result_review`, `review_finding`). Use wire **`schema_version`** **1.2.0** for those requests/responses; they are analysis/review workflows, not MAT-1 git ops.

6. **Gumloop runner (MAT-5)**: Gumloop’s **`start_pipeline`** API can kick off flows whose **HTTP** nodes forward bodies validated against MAT-1/MAT-2 schemas; use shared **`correlation_id`** across steps. See **`docs/prototypes/mat-5-gumloop.md`** and **`examples/gumloop/`**.

7. **CLI delegation (ADR 0002)**: Agents are invoked via CLI tools (`claude`, `codex`, `gemini`), not direct API calls. No API keys required — each CLI uses its own license/subscription. MAT-16 defines which CLI handles which role.

8. **Agent definitions (MAT-17)**: Agents are defined as Markdown files in `agents/` with YAML frontmatter. The frontmatter specifies identity (`name`, `description`), role (`orchestrator` / `worker` / `executor`), CLI binding, allowed MAT-2 ops, and optional tools. The Markdown body is the system prompt. See `docs/agent-definition-format.md`.

9. **Runtime adapter (MAT-18)**: `mat_runtime/` Python module provides `AgentRouter` class that loads agent definitions and MAT-16 config, then routes MAT-2 requests to CLI adapters. Run with `python -m mat_runtime invoke --agent coder --instruction "..."` or `python -m mat_runtime list-agents`. Unit tests in `mat_runtime/tests/`.

10. **Skill naming (ADR 0003)**: Skills use **domain-specific names** (`/develop`, `/review-pr`, `/test`) rather than generic names (`/invoke-agent`). This aligns with AI Fluency Insights pattern matching and improves discoverability. `/develop` orchestrates the full team; single-agent skills bypass the orchestrator for focused tasks.

11. **MCP & tool capabilities (ADR 0004)**: Integration-dependent operations (tickets, Slack, external APIs) run in the **orchestrator context** — workers don't inherit MCPs. Agent definitions may declare tool restrictions (e.g., reviewer can't edit). v1 keeps MCPs at orchestrator level; v2 may add MCP inheritance or shared config.

## Related codebases

- **Minions**: `~/org/ai-tools/scripts/minions/` — Jira→PR pipeline; reference for stages, not a hard dependency.
- **Claude introspection**: `~/org/claude-code/plugins/claude-introspection/` — fluency skill; see MAT-10.

## Suggested next steps (in order)

1. **`git checkout main`**, **`git pull origin main`** (see **Sync the repo** above).
2. **Run all eight validation scripts** (see **Validation** below) and confirm green.
3. When prioritized, pick up **MAT-20** (consumer repo documentation) or **MAT-7** (audit checklist).
4. **Remaining backlog:** MAT-7, MAT-20, MAT-21, MAT-24.

## Validation

```bash
cd /path/to/multi-agent-toolkit
python3 -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
python scripts/validate_gemini_git_ops.py
python scripts/validate_codex_code_exec.py
python scripts/validate_ai_team_repo_profile.py
python scripts/validate_orchestrator_state.py
python scripts/validate_hitl_asana_approval.py
python scripts/validate_provider_config.py
python scripts/validate_agent_definitions.py
python scripts/validate_gumloop_examples.py
python -m pytest mat_runtime/tests/ -v   # MAT-18 runtime tests
```

Optional: `export MAT_GEMINI_GIT_OPS_V1=/path/to/schemas/gemini-git-ops/v1`, `export MAT_CODEX_CODE_EXEC_V1=/path/to/schemas/codex-code-exec/v1`, `export MAT_AI_TEAM_REPO_PROFILE_V1=/path/to/schemas/ai-team-repo-profile/v1`, `export MAT_ORCHESTRATOR_STATE_V1=/path/to/schemas/orchestrator-state/v1`, `export MAT_HITL_ASANA_APPROVAL_V1=/path/to/schemas/hitl-asana-approval/v1`, `export MAT_PROVIDER_CONFIG_V1=/path/to/schemas/provider-config/v1`, or `export MAT_AGENT_DEFINITION_V1=/path/to/schemas/agent-definition/v1` if a bundle is not at the default `root_relative` path.

## References

- Notion tickets: `$MAT_NOTION_TICKETS_URL` (set in your local environment)
- Notion parent hub: `$MAT_NOTION_HUB_URL` (set in your local environment)
- Research: `research/multi-agent-research.md`
