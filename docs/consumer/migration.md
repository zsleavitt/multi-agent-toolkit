# Migration from other setups

MAT standardizes **wire formats** (MAT-1 git, MAT-2 code worker), **repo profile** (MAT-9), **CLI routing** (MAT-16), and **slash skills**. You can adopt it incrementally.

## From “Cursor agent only” or generic IDE chat

**Before:** Ad-hoc prompts, no shared request JSON, no allowlisted git bridge.

**After:**

1. Add **`ai-team.repo.json`** for portable identity and optional tickets.
2. Add **`mat-config.json`** if you use `mat_runtime` with multiple CLIs.
3. Install **[Cursor rules](installing-skills.md)** and point script paths at your MAT checkout.
4. Keep **orchestration** in the main session; route implementation and git through MAT-2 / MAT-1 shaped tools or CLIs per [ADR 0002](../../docs/adr/0002-cli-delegation-vs-direct-api.md).

## From GitHub Copilot Chat (no repo profile)

**Map:** Copilot stays an assistant; MAT gives you **schemas**, **validators**, and **skills** that do not depend on a single vendor API.

**Steps:** Vendor MAT; add `ai-team.repo.json` + skills; optionally keep Copilot for inline completion while using `/develop` for structured multi-agent work.

## From direct OpenAI / Anthropic API scripts

**Before:** Custom HTTP clients, keys in env, bespoke JSON.

**After:** Prefer **CLI delegation** (Codex / Claude Code / Gemini CLIs) so auth and billing stay with each tool’s supported flow. Replace ad-hoc payloads with **MAT-1/MAT-2** request objects validated against this repo’s schemas.

**Migration tip:** Port one workflow at a time — e.g. implement step only — and validate payloads with `scripts/validate_codex_code_exec.py` fixtures before swapping the transport.

## From Jenkins / GitLab CI “run this prompt”

**Before:** CI echoes a prompt into a single model call.

**After:**

- Run **`python -m mat_runtime invoke`** with a checked-in request JSON.
- Use **`python -m mat_runtime smoke`** (or `--strict`) in pipeline images that must include CLIs.
- Keep secrets out of MAT JSON; CLIs use their own auth on the runner.

## From internal “agent router”

**Map your concepts:**

| Common pattern | MAT equivalent |
|----------------|----------------|
| Repo metadata / org URLs | `ai-team.repo.json` (MAT-9) |
| Which backend handles coding | `mat-config.json` agents + routing (MAT-16) |
| Git automation | MAT-1 + git executor CLI |
| Code changes / tests | MAT-2 + worker CLI |
| Orchestrator memory | `schemas/orchestrator-state/v1/` (MAT-4 / MAT-10) |

You can keep your outer orchestrator and emit MAT-1/MAT-2 JSON into existing CLIs.

## Rollback

MAT is **additive**. Remove `.cursorrules` entries, delete `ai-team.repo.json` / `mat-config.json`, and stop calling `mat_runtime` — your codebase does not depend on MAT at compile time.
