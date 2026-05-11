# ADR 0005: Smoke checks for local CLI toolchains (Codex, Gemini, Claude, …)

## Status

Accepted

## Context

The MAT runtime (`AgentRouter` → per-agent `CLIAdapter` → subprocess) is the only supported path for delegating to **Claude Code**, **OpenAI Codex**, **Google Gemini**, and similar tools (see ADR 0002). That stack must be verifiable on a developer or automation host before relying on **skills** (`/review-pr`, `/develop`, …) or **crew**/**swarm** flows that assume workers respond correctly.

We need two levels of check:

1. **Fast, non-interactive, no token usage** — binary on `PATH`, `--version` works (including the “mise shim but not activated” case), agents load, MAT-16 config (if any) is valid separately via existing validators.
2. **End-to-end, opt-in, billable/usage** — a minimal MAT-2 request actually reaches the default adapter (`codex exec`, `claude --print`, `gemini --prompt`, …) and returns an `ok` `MAT2Response` so the wiring and auth for that CLI are definitively working.

## Decision

- Add **`python -m mat_runtime smoke`**, implemented in `mat_runtime/smoke.py`, with:
  - **Default (dry)**: for each `cli` that appears in `agents/*.md` and is registered in `ADAPTER_REGISTRY` (`claude`, `codex`, `gemini`, …), run a **PATH + `--version` preflight** and print a per-row status. Exits `0` by default even if a tool is missing (so “partial installs” are still easy to work with), unless **`--strict`** is passed (e.g. CI that installs all CLIs in the test image).
  - **Live (`--real`)**: only when **`MAT_SMOKE_REAL_CLI=1`** is set in the environment, run one or more **`AgentRouter.invoke(...)`** calls with a **tiny, non-destructive instruction** and a **MAT-2 `op` chosen to prefer `codex.review` / `codex.diagnose` / …** so side effects are minimized. Refuse `--real` if `MAT_SMOKE_REAL_CLI` is set to a falsy disable token (`0`, `false`, …) or if `MAT_SMOKE_REAL_CLI` is not exactly `1` (belt-and-suspenders against accidental runs in scripts).
  - Modes: **`--real --agent reviewer`** (single agent) or **`--real --per-cli`** (one **representative** agent per unique CLI, e.g. `coder` for `codex`, `researcher` for `gemini`, `orchestrator` for `claude`).

- **Default CI and `bin/setup`**: keep running **unit tests** with **mocks** (no real CLIs) and `scripts/validate_*.py`. Do **not** add `--real` to default CI without a controlled image, credentials, and a separate job name.

- **Contract**: “Working” is defined as **`MAT2Response.ok` + structured `result` or `error`**, not raw log scraping, consistent with the rest of `mat_runtime`.

## Consequences

- Developers and release automation have a **documented, repeatable** way to prove adapters work after OS upgrades, `mise` changes, or new laptops.
- **Token/cost and flakes** are explicit: real checks require **`MAT_SMOKE_REAL_CLI=1`**; dry checks remain cheap and safe in every pipeline.
- If a new `cli` value is added to `agents/`, the dry preflight will include it when it is added to `ADAPTER_REGISTRY` and a representative agent is chosen for `--per-cli` in `_PREFERRED_AGENT_BY_CLI` (extend when adding tools).

## References

- [ADR 0002](0002-cli-delegation-vs-direct-api.md) — CLI delegation vs API
- [MAT-16](../../schemas/provider-config/v1/) — `mat-config.json` / `.mat/config.json`
- `mat_runtime/adapters/`, `mat_runtime/router.py`, `mat_runtime/__main__.py` (`smoke` subcommand)
