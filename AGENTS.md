# Multi-Agent Toolkit — Codex agent instructions

**Audience:** You are using [OpenAI Codex](https://openai.com/codex) (CLI or IDE) in this repository.

This file **complements** `CLAUDE.md`; it does **not** replace it. `CLAUDE.md` is written for the **Claude Code** orchestrator session. Here we only orient **MAT-2** workers (Codex).

## Your role (MAT-2)

| You do | You do not |
|--------|------------|
| Implement, test, refactor, diagnose, and review code under scoped MAT-2 work | Change MAT JSON contracts or invent new `op` strings without schema updates |
| Follow `agents/*.md`, schemas, and repo conventions | Run **MAT-1** git operations (branch, fetch, pull, push, staging, commits, diffs) as your own policy — those go through the orchestrator and a **MAT-1** executor |

**MAT-1** — `schemas/gemini-git-ops/v1/` — allowlisted git / CLI executor requests.  
**MAT-2** — `schemas/codex-code-exec/v1/` — Codex worker requests and responses.

## Read next

| Path | Purpose |
|------|---------|
| `CLAUDE.md` | Orchestrator contract, full role table, schema index (stay aligned with this) |
| `agents/` | Agent definitions (`coder.md`, `reviewer.md`, `tester.md`, …) and `agents/README.md` |
| `schemas/` | All MAT bundles (MAT-1, MAT-2, MAT-16 provider config, …) |
| `.codex/README.md` | Codex hooks, trust model, optional guardrails |
| `adapters/codex/README.md` | Adapter overview, `bin/setup` / user `~/.codex` notes |

## Hooks

Extra context may be injected from `.codex/` (see `.codex/README.md`). Enable **`codex_hooks`** in your user `~/.codex/config.toml` (Windows: `%USERPROFILE%\.codex\config.toml`), run **`codex auth`** when needed, and **trust** this repo so project hooks load.

---

Keep this file **short** and let `CLAUDE.md` remain the canonical orchestration contract.
