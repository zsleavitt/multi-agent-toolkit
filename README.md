# Multi-Agent Toolkit

Portable contracts and tooling for a **Claude Code–orchestrated** dev loop: planning and routing stay in Claude; **Codex** (or similar) handles scoped implementation; **Gemini** (or another runner) executes **allowlisted git/CLI** work. The goal is a **repo-agnostic** setup driven by config and JSON Schemas, not hardcoded org URLs or paths.

## Quick Start

```bash
git clone https://github.com/zsleavitt/multi-agent-toolkit.git
cd multi-agent-toolkit
bin/setup
```

The setup script will:
1. Create a Python virtual environment
2. Install dependencies
3. Check for CLI tools (claude, codex, gemini)
4. Run schema validators and tests

## Prerequisites

### Required

- **Python 3.10+** — for schema validation and runtime

### Optional (for mat_runtime)

The runtime adapter invokes AI agents via CLI tools. Install the ones you need:

| CLI | Purpose | Install |
|-----|---------|---------|
| `claude` | Claude Code — orchestration, planning, review | [docs.anthropic.com](https://docs.anthropic.com/en/docs/claude-code) |
| `codex` | OpenAI Codex — code implementation, testing | [github.com/openai/codex-cli](https://github.com/openai/codex-cli) |
| `gemini` | Google Gemini — research, git operations | [github.com/google/gemini-cli](https://github.com/google/gemini-cli) |

Per **ADR 0002**, agents are invoked via CLI delegation — no API keys required. Each CLI manages its own authentication.

Check your setup:

```bash
bin/setup --check
```

## Runtime Usage

The `mat_runtime` module routes MAT-2 requests to CLI agents:

```bash
# List available agents
python -m mat_runtime list-agents

# Invoke an agent directly
python -m mat_runtime invoke --agent coder --instruction "Add a hello world function"

# Invoke with a MAT-2 request file
python -m mat_runtime invoke --request request.json
```

### Verifying local CLI toolchains (Codex, Gemini, …)

1. **Dry preflight (no API usage)** — `PATH` + `--version` for each adapter CLI used in `agents/`:

   ```bash
   python -m mat_runtime smoke
   ```

2. **Strict** — exit with failure if any expected CLI is missing (for images that should have every tool):

   ```bash
   python -m mat_runtime smoke --strict
   ```

3. **End-to-end (opt-in, billable)** — requires `MAT_SMOKE_REAL_CLI=1` and runs a minimal `AgentRouter.invoke` (e.g. single reviewer or one agent per tool):

   ```bash
   export MAT_SMOKE_REAL_CLI=1
   python -m mat_runtime smoke --real --agent reviewer
   # or:  python -m mat_runtime smoke --real --per-cli
   ```

Details: [docs/adr/0005-smoke-cli-verification.md](docs/adr/0005-smoke-cli-verification.md).

## Layout

| Path | Purpose |
|------|---------|
| `bin/setup` | Setup script — creates venv, installs deps, checks CLI tools |
| `mat_runtime/` | **MAT-18** — Runtime adapter layer with `AgentRouter` class; `python -m mat_runtime smoke` for CLI preflight |
| `agents/` | **MAT-17** — Core agent definitions (orchestrator, coder, researcher, reviewer, security, tester) |
| `crews/` | **MAT-42** — Crew definitions (named agent collections with routing) |
| `swarms/` | **MAT-45** — Swarm definitions (parallel dispatch with consensus) |
| `lib/skills/` | **MAT-19+** — Shared skill implementations; `.claude/skills/` and `.cursor/skills/` hold platform stubs (see `lib/skills/README.md`) |
| `adapters/` | Tool-specific discovery manifests (Claude Code, Cursor) |
| `schemas/gemini-git-ops/v1/` | **MAT-1** — Git operations request/response schemas |
| `schemas/codex-code-exec/v1/` | **MAT-2** — Code execution request/response schemas |
| `schemas/provider-config/v1/` | **MAT-16** — CLI-based agent configuration |
| `schemas/agent-definition/v1/` | **MAT-17** — Agent definition frontmatter schema |
| `schemas/crew/v1/` | **MAT-42** — Crew definition schema |
| `schemas/swarm/v1/` | **MAT-45** — Swarm definition schema |
| `schemas/ai-team-repo-profile/v1/` | **MAT-9** — Portable repo profile + work-item adapters |
| `schemas/orchestrator-state/v1/` | **MAT-4/10** — Orchestrator state (queue, artifacts, checkpoints) |
| `schemas/hitl-asana-approval/v1/` | **MAT-6** — Asana HITL trigger and callback JSON |
| `config/schema-registry.json` | Schema bundle paths and env overrides |
| `docs/adr/` | Architecture decision records |
| `docs/agent-definition-format.md` | Agent definition specification |
| `scripts/validate_*.py` | Schema validators (10 total) |
| `CLAUDE.md` | Orchestrator context for Claude Code sessions |
| `CURSOR_HANDOFF.md` | Editor handoff documentation |

## Validation

Run all validators:

```bash
source .venv/bin/activate
python scripts/validate_gemini_git_ops.py
python scripts/validate_codex_code_exec.py
python scripts/validate_ai_team_repo_profile.py
python scripts/validate_orchestrator_state.py
python scripts/validate_hitl_asana_approval.py
python scripts/validate_provider_config.py
python scripts/validate_agent_definitions.py
python scripts/validate_crew.py
python scripts/validate_swarm.py
python scripts/validate_gumloop_examples.py
python -m pytest mat_runtime/tests/ -v
```

Or use the setup script:

```bash
bin/setup  # Runs all validators and tests
```

## Architecture

```
┌─────────────────┐
│   Orchestrator  │  (Claude Code CLI)
│   - planning    │
│   - routing     │
│   - synthesis   │
└────────┬────────┘
         │ MAT-2 JSON
         ▼
┌─────────────────┐
│     Worker      │  (Codex CLI)
│   - implement   │
│   - test        │
│   - refactor    │
│   - diagnose    │
│   - review      │
└────────┬────────┘
         │ MAT-1 JSON
         ▼
┌─────────────────┐
│  Git Executor   │  (Gemini CLI)
│   - git ops     │
│   - research    │
└─────────────────┘
```

Each arrow represents a **wire format** (MAT-1/MAT-2 JSON). CLI tools translate these into native operations.

## Status

| Schema | Description | Status |
|--------|-------------|--------|
| MAT-1 | Git executor contracts | Done |
| MAT-2 | Code worker contracts | Done |
| MAT-4 | Orchestrator state | Done |
| MAT-6 | HITL Asana approval | Done |
| MAT-9 | Repo profile + adapters | Done |
| MAT-16 | CLI-based agent config | Done |
| MAT-17 | Agent definitions | Done |
| MAT-18 | Runtime adapter | Done |
| MAT-42 | Crew schema (agent collections) | Done |
| MAT-45 | Swarm schema (parallel dispatch) | Done |

See `CURSOR_HANDOFF.md` for full ticket status.

## Security

### Dependency management

Dependencies are **pinned with SHA-256 hashes** to prevent supply chain attacks:

```bash
pip install --require-hashes -r requirements-dev.txt
```

### CLI delegation (ADR 0002)

- No API keys in this repo — each CLI manages its own auth
- Avoids duplicate billing beyond existing CLI subscriptions
- Enterprise-compatible (SSO, audit logging via CLI tools)

### Schema security

- Operations are **enum-constrained** and **deny-by-default** via `manifest.json`
- Input validation uses `additionalProperties: false`
- `repo_root` validated as absolute path (MAT-23)

## Principles

1. **Deny-by-default** — only `manifest.json` → `allowed_operations`
2. **No shell in git bridge** — fixed `git` argv only
3. **Portable paths** — `repo_root` and bundle paths via config/env
4. **CLI delegation** — invoke tools, don't embed API clients
