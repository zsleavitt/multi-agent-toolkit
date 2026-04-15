# Multi-agent toolkit

Portable contracts and tooling for a **Claude Code–orchestrated** dev loop: planning and routing stay in Claude; **Codex** (or similar) handles scoped implementation; **Gemini** (or another runner) executes **allowlisted git/CLI** work. The goal is a **repo-agnostic** setup driven by config and JSON Schemas, not hardcoded org URLs or paths.

## Layout

| Path | Purpose |
|------|---------|
| `config/schema-registry.json` | Where schema bundles live on disk (`root_relative`); optional `published_document_base` for future publish/mirror tooling only. |
| `schemas/gemini-git-ops/v1/` | **MAT-1** — request/response JSON Schemas for git operations (`manifest.json`, `request.schema.json`, `response.schema.json`, `examples/`). |
| `scripts/validate_gemini_git_ops.py` | Validates examples against MAT-1 schemas (see below). |
| `research/multi-agent-research.md` | Design notes and citations for orchestration patterns, cost, and verification. |

## Prerequisites (schema validation)

```bash
python3 -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
python scripts/validate_gemini_git_ops.py
```

Override the MAT-1 bundle directory:

```bash
export MAT_GEMINI_GIT_OPS_V1=/absolute/path/to/schemas/gemini-git-ops/v1
python scripts/validate_gemini_git_ops.py
```

## Status

- **MAT-1** (Gemini git/CLI contracts): schemas and examples in tree; see `schemas/gemini-git-ops/v1/README.md`.
- Further tickets (Codex contracts, `CLAUDE.md`, state, Gumloop, HITL, repo profile) are tracked in your Notion **Multi-Agent Toolkit** board.

## Principles

- **Deny-by-default** executors: only `manifest.json` → `allowed_operations`.
- **No shell** in git bridge: fixed `git` argv only.
- **Portable** `repo_root` and bundle paths via config/env — no implicit cwd for orchestration.
