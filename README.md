# Multi-agent toolkit

Portable contracts and tooling for a **Claude Code–orchestrated** dev loop: planning and routing stay in Claude; **Codex** (or similar) handles scoped implementation; **Gemini** (or another runner) executes **allowlisted git/CLI** work. The goal is a **repo-agnostic** setup driven by config and JSON Schemas, not hardcoded org URLs or paths.

## Layout

| Path | Purpose |
|------|---------|
| `config/schema-registry.json` | Where schema bundles live on disk (`root_relative`); optional `published_document_base` for future publish/mirror tooling only. |
| `schemas/gemini-git-ops/v1/` | **MAT-1** — git operations request/response schemas; optional **`timeout_ms`** (MAT-11); staging/commit/diff ops (**MAT-12**); `manifest.json` + `examples/`. |
| `schemas/codex-code-exec/v1/` | **MAT-2** — code execution request/response schemas; optional session + **`timeout_ms`** (MAT-14); **`codex.diagnose` / `codex.review`** (MAT-13, **`schema_version`** 1.2.0); `manifest.json` + `examples/`. |
| `schemas/ai-team-repo-profile/v1/` | **MAT-9** — portable repo profile (`ai-team.repo.json` / YAML) + work-item adapter (Linear, Jira, GitHub Issues, file, none). |
| `schemas/orchestrator-state/v1/` | **MAT-4** / **MAT-10** — orchestrator persisted state (`orchestrator.state.json`): queue, artifact index, checkpoints; optional orchestrator session + fluency metadata; repo-relative paths. |
| `schemas/hitl-asana-approval/v1/` | **MAT-6** — Asana HITL trigger and callback JSON for `blocked_hitl` queue gates. |
| `scripts/validate_gemini_git_ops.py` | Validates examples against MAT-1 schemas (see below). |
| `scripts/validate_codex_code_exec.py` | Validates examples against MAT-2 schemas. |
| `scripts/validate_ai_team_repo_profile.py` | Validates examples against MAT-9 `repo-profile.schema.json`. |
| `scripts/validate_orchestrator_state.py` | Validates examples against MAT-4 `orchestrator-state.schema.json`. |
| `scripts/validate_hitl_asana_approval.py` | Validates examples against MAT-6 trigger and callback schemas. |
| `scripts/gumloop_start_pipeline.py` | MAT-5: optional stdlib helper to call Gumloop `start_pipeline` (requires API env vars). |
| `docs/adr/` | Architecture decision records (e.g. primary orchestrator). |
| `docs/prototypes/` | Exploratory integrations (e.g. **MAT-5** Gumloop runner handoff). |
| `examples/gumloop/` | MAT-5: Gumloop `start_pipeline` example + Input node naming conventions. |
| `CLAUDE.md` | Orchestrator-only context for Claude Code sessions using this toolkit. |
| `research/multi-agent-research.md` | Design notes and citations for orchestration patterns, cost, and verification. |

## Prerequisites (schema validation)

```bash
python3 -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
python scripts/validate_gemini_git_ops.py
python scripts/validate_codex_code_exec.py
python scripts/validate_ai_team_repo_profile.py
python scripts/validate_orchestrator_state.py
python scripts/validate_hitl_asana_approval.py
python scripts/validate_gumloop_examples.py
```

Override the MAT-1 bundle directory:

```bash
export MAT_GEMINI_GIT_OPS_V1=/absolute/path/to/schemas/gemini-git-ops/v1
python scripts/validate_gemini_git_ops.py
```

Override the MAT-2 bundle directory:

```bash
export MAT_CODEX_CODE_EXEC_V1=/absolute/path/to/schemas/codex-code-exec/v1
python scripts/validate_codex_code_exec.py
```

Override the MAT-9 bundle directory:

```bash
export MAT_AI_TEAM_REPO_PROFILE_V1=/absolute/path/to/schemas/ai-team-repo-profile/v1
python scripts/validate_ai_team_repo_profile.py
```

Override the MAT-4 bundle directory:

```bash
export MAT_ORCHESTRATOR_STATE_V1=/absolute/path/to/schemas/orchestrator-state/v1
python scripts/validate_orchestrator_state.py
```

Override the MAT-6 bundle directory:

```bash
export MAT_HITL_ASANA_APPROVAL_V1=/absolute/path/to/schemas/hitl-asana-approval/v1
python scripts/validate_hitl_asana_approval.py
```

## Status

- **MAT-1** (Gemini git/CLI contracts): schemas and examples in tree; see `schemas/gemini-git-ops/v1/README.md`.
- **MAT-2** (Codex code execution contracts): `schemas/codex-code-exec/v1/README.md`.
- **MAT-9** (portable repo profile + work-item adapter): `schemas/ai-team-repo-profile/v1/README.md`.
- **MAT-4** / **MAT-10** (orchestrator state; sessions + fluency): `schemas/orchestrator-state/v1/README.md`.
- **MAT-6** (Asana HITL triggers and callbacks): `schemas/hitl-asana-approval/v1/README.md`.
- **MAT-3** / **MAT-8**: root `CLAUDE.md` and `docs/adr/0001-primary-orchestrator-claude-code-vs-cursor.md`.
- **MAT-5** (Gumloop prototype): `docs/prototypes/mat-5-gumloop.md`, `examples/gumloop/`, `scripts/gumloop_start_pipeline.py`.
- Further tickets are tracked in your Notion **Multi-Agent Toolkit** board (remaining P2: **MAT-7**).

## Principles

- **Deny-by-default** executors: only `manifest.json` → `allowed_operations`.
- **No shell** in git bridge: fixed `git` argv only.
- **Portable** `repo_root` and bundle paths via config/env — no implicit cwd for orchestration.
