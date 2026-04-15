# Multi-Agent Toolkit — orchestrator context (Claude Code)

Use this file in the **Claude Code** session that **orchestrates** work across workers. It is not a substitute for project-specific `CLAUDE.md` files in application repos; it defines **role boundaries and contracts** for this toolkit repository and any consumer repo that adopts the same split.

## Roles

| Role | Responsibility | Does **not** |
|------|----------------|--------------|
| **Claude Code (this session)** | Plan, decompose, route, synthesize; emit **validated JSON** to tools; review outcomes | Run allowlisted git argv (use MAT-1 executor); run Codex sandboxes directly unless your deployment explicitly allows it |
| **Codex (or equivalent)** | Scoped **implement / test / refactor** under MAT-2 requests | Define wire formats; own repo-wide git policy |
| **Gemini-style executor** | MAT-1 **deny-by-default** git ops; **no shell** in the git bridge | Invent new `op` strings without updating schemas + manifest |

## Contracts (schemas)

- **MAT-1** — `schemas/gemini-git-ops/v1/` — git/CLI executor requests/responses; `manifest.json` allowlist.
- **MAT-2** — `schemas/codex-code-exec/v1/` — code worker requests/responses; optional **session** + **turn** for multi-turn runs.
- **MAT-9** — `schemas/ai-team-repo-profile/v1/` — portable **`ai-team.repo.json`** (or YAML → same shape): identity, repo-relative paths, **work_item_source** adapter (`none` | `linear` | `jira` | `github_issues` | `file`).
- **MAT-4** — `schemas/orchestrator-state/v1/` — durable **`orchestrator.state.json`**: **queue**, **artifacts**, **checkpoints**; repo-relative paths (align with MAT-9 `path_overrides.artifacts_dir` / `agent_state_dir`).
- **Registry** — `config/schema-registry.json` — on-disk bundle paths; env overrides documented in each bundle’s README.

Validation:

```bash
source .venv/bin/activate
python scripts/validate_gemini_git_ops.py
python scripts/validate_codex_code_exec.py
python scripts/validate_ai_team_repo_profile.py
python scripts/validate_orchestrator_state.py
```

## Design defaults

1. **Git vs code scope** — Branch/worktree/fetch/pull/push style ops are MAT-1. Whether `git add` / `commit` / `diff` live on the executor, the code worker, or both is **explicitly deferred** — track under **MAT-12** so MAT-2 stays code-execution scoped.
2. **Primary orchestrator** — See `docs/adr/0001-primary-orchestrator-claude-code-vs-cursor.md` (Claude Code is normative for toolkit semantics; other editors remain supported).
3. **Portability** — Requests carry **`repo_root`** (absolute). Avoid implicit cwd in orchestration; **MAT-9** repo profiles supply identity, repo-relative path hints, and a **work-item adapter** — not another machine’s absolute paths or baked-in org URLs.

## Handoff

For Cursor-specific pickup steps and the Notion ticket board, read **`CURSOR_HANDOFF.md`**.
