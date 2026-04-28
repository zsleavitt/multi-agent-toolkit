# MAT-7 — Repository audit vs architecture checklist

**Date:** 2026-04-28  
**Issue:** [GitHub #27](https://github.com/zsleavitt/multi-agent-toolkit/issues/27)

## Schema registry ↔ manifests ↔ validators

| `schema-registry.json` key | `root_relative` | `manifest.json` | Validator script |
|----------------------------|-----------------|-----------------|------------------|
| `gemini-git-ops@v1` | `schemas/gemini-git-ops/v1` | yes | `scripts/validate_gemini_git_ops.py` |
| `codex-code-exec@v1` | `schemas/codex-code-exec/v1` | yes | `scripts/validate_codex_code_exec.py` |
| `ai-team-repo-profile@v1` | `schemas/ai-team-repo-profile/v1` | yes | `scripts/validate_ai_team_repo_profile.py` |
| `orchestrator-state@v1` | `schemas/orchestrator-state/v1` | yes | `scripts/validate_orchestrator_state.py` |
| `hitl-asana-approval@v1` | `schemas/hitl-asana-approval/v1` | yes | `scripts/validate_hitl_asana_approval.py` |
| `provider-config@v1` | `schemas/provider-config/v1` | yes | `scripts/validate_provider_config.py` |
| `agent-definition@v1` | `schemas/agent-definition/v1` | yes | `scripts/validate_agent_definitions.py` |
| `crew@v1` | `schemas/crew/v1` | yes | `scripts/validate_crew.py` |
| `swarm@v1` | `schemas/swarm/v1` | yes | `scripts/validate_swarm.py` |

**Not in registry (by design):** `scripts/validate_gumloop_examples.py` validates **MAT-5** `examples/gumloop/` and embedded MAT-2 payloads. Gumloop is a prototype integration, not a published schema bundle key.

## Agent definitions (MAT-17)

- All `agents/*.md` and `agents/variants/*.md` pass `validate_agent_definitions.py` after aligning **MAT-16 / MAT-17** `cli` enums with runtime: **`codex-review`** added to `agent-frontmatter.schema.json` and `provider-config.schema.json` so `agents/reviewer.md` matches `mat_runtime` (`CodexReviewAdapter`).
- Documentation tables (`docs/agent-definition-format.md`, `agents/README.md`, `schemas/agent-definition/v1/README.md`, `schemas/provider-config/v1/README.md`) updated so the reviewer agent lists **`codex-review`**, not `claude`, for the canonical `agents/reviewer.md` binding.

## Validation wiring

- **`bin/setup`** `run_validators()` now includes `validate_crew.py` and `validate_swarm.py` (previously omitted vs README / `CLAUDE.md`).
- **`CURSOR_HANDOFF.md`** validator count, validation commands, optional env vars (`MAT_CREW_V1`, `MAT_SWARM_V1`), repository layout (`lib/skills/`, crew/swarm paths), and backlog pointers were brought in line with `CLAUDE.md` and `README.md`.

## Test suite

- **`mat_runtime/tests/test_adapters.py`:** `CodexAdapter` uses the global `codex exec` argv shape; the test still expected the older `npx` wrapper. Renamed and updated assertions to match `mat_runtime/adapters/codex.py`.

## Verification (local)

All ten `scripts/validate_*.py` scripts and `python3 -m pytest mat_runtime/tests/` were run successfully after these changes.

## Residual / follow-up

- **Ticket board table** in `CURSOR_HANDOFF.md` remains a curated snapshot; authoritative status is [GitHub Issues](https://github.com/zsleavitt/multi-agent-toolkit/issues) (row `MAT-41+` added as pointer).
- **No separate follow-up issues** filed from this audit: fixes were applied in-repo.
