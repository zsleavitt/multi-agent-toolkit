# Multi-Agent Toolkit — orchestrator context (Claude Code)

Use this file in the **Claude Code** session that **orchestrates** work across workers. It is not a substitute for project-specific `CLAUDE.md` files in application repos; it defines **role boundaries and contracts** for this toolkit repository and any consumer repo that adopts the same split.

## Roles

| Role | Responsibility | Does **not** |
|------|----------------|--------------|
| **Claude Code (this session)** | Plan, decompose, route, synthesize; emit **validated JSON** to tools; review outcomes | Run allowlisted git argv (use MAT-1 executor); run Codex sandboxes directly unless your deployment explicitly allows it |
| **Codex (or equivalent)** | Scoped **implement / test / refactor / diagnose / review** under MAT-2 requests | Define wire formats; own repo-wide git policy |
| **Gemini-style executor** | MAT-1 **deny-by-default** git ops; **no shell** in the git bridge | Invent new `op` strings without updating schemas + manifest |

## Contracts (schemas)

- **MAT-1** — `schemas/gemini-git-ops/v1/` — git/CLI executor requests/responses; `manifest.json` allowlist; optional **`timeout_ms`** (MAT-11, **`schema_version`** 1.1.0); staging/commit/diff ops (**MAT-12**: `git.add`, `git.commit`, `git.diff`).
- **MAT-2** — `schemas/codex-code-exec/v1/` — code worker requests/responses; optional **session** + **turn** for multi-turn runs; optional **`timeout_ms`** (MAT-14, **`schema_version`** 1.1.0); **`codex.diagnose`** / **`codex.review`** + structured results (MAT-13, **`schema_version`** 1.2.0).
- **MAT-9** — `schemas/ai-team-repo-profile/v1/` — portable **`ai-team.repo.json`** (or YAML → same shape): identity, repo-relative paths, **work_item_source** adapter (`none` | `linear` | `jira` | `github_issues` | `file`).
- **MAT-4** — `schemas/orchestrator-state/v1/` — durable **`orchestrator.state.json`**: **queue**, **artifacts**, **checkpoints**; repo-relative paths (align with MAT-9 `path_overrides.artifacts_dir` / `agent_state_dir`).
- **MAT-10** — same bundle — optional **`orchestrator_session`** (primary Claude Code session) and checkpoint **`fluency`** (`planning` / `review` / …) for **`/ai-fluency-insights`**-style tooling; keep high-signal planning and review in this orchestrator session when fluency scores matter.
- **MAT-6** — `schemas/hitl-asana-approval/v1/` — **trigger** and **callback** JSON for Asana-backed approvals when MAT-4 queue status is **`blocked_hitl`** (correlation + `queue_item_id` threading).
- **MAT-16** — `schemas/provider-config/v1/` — model-agnostic **LLM provider configuration**: providers map, **model_aliases** (semantic names like `orchestrator`, `worker`), fallback chains, budgets. Auth via env var references only (no secrets in config).
- **Registry** — `config/schema-registry.json` — on-disk bundle paths; env overrides documented in each bundle’s README.

Validation:

```bash
source .venv/bin/activate
python scripts/validate_gemini_git_ops.py
python scripts/validate_codex_code_exec.py
python scripts/validate_ai_team_repo_profile.py
python scripts/validate_orchestrator_state.py
python scripts/validate_hitl_asana_approval.py
python scripts/validate_provider_config.py
python scripts/validate_gumloop_examples.py
```

## Design defaults

1. **Git vs code scope (MAT-12)** — Branch/worktree/fetch/pull/push **and** working-tree staging/commits/diffs (`git.add`, `git.commit`, `git.diff`) are **MAT-1** allowlisted ops. **MAT-2** covers worker ops (`codex.implement` / `codex.test` / `codex.refactor` / **`codex.diagnose`** / **`codex.review`**, MAT-13) but **not** git staging, commits, or diff on the wire — the orchestrator issues MAT-1 JSON for those.
2. **Primary orchestrator** — See `docs/adr/0001-primary-orchestrator-claude-code-vs-cursor.md` (Claude Code is normative for toolkit semantics; other editors remain supported).
3. **Portability** — Requests carry **`repo_root`** (absolute). Avoid implicit cwd in orchestration; **MAT-9** repo profiles supply identity, repo-relative path hints, and a **work-item adapter** — not another machine’s absolute paths or baked-in org URLs.
4. **Fluency (MAT-10)** — When using introspection-based fluency, run **`/ai-fluency-insights`** (or equivalent) in this **main** session; persist optional **`fluency`** on MAT-4 checkpoints and **`orchestrator_session`** on the state document so automation can correlate exports with orchestration phases.

## Handoff

For Cursor-specific pickup steps and the Notion ticket board, read **`CURSOR_HANDOFF.md`**. For running MAT contracts behind **Gumloop** flows (HTTP runner prototype), read **`docs/prototypes/mat-5-gumloop.md`**.
