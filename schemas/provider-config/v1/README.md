# MAT-16 — Agent configuration schema (`v1`)

Versioned JSON Schema for **CLI-based agent configuration**. This schema defines which CLI tools handle which roles in multi-agent orchestration — **no API keys required**.

See **ADR 0002** (`docs/adr/0002-cli-delegation-vs-direct-api.md`) for architectural rationale.

## Schema identity (vendor-neutral)

- Same rules as other MAT bundles: **fragment `$ref` only** inside the schema file.
- **`manifest.json`** uses `bundle_id` `provider-config@v1`.

## Repo config (`config/schema-registry.json`)

| Field | Purpose |
|-------|---------|
| `schema_bundles["provider-config@v1"].root_relative` | Directory for this bundle. |
| `MAT_PROVIDER_CONFIG_V1` | Env override for validators (absolute path to this `v1` folder). |

## Files in this folder

| File | Purpose |
|------|---------|
| `manifest.json` | Bundle metadata and notes. |
| `provider-config.schema.json` | Main schema for agent configuration documents. |
| `examples/` | Valid / invalid fixtures for CI. |

## CLI delegation model

The toolkit uses **CLI delegation** instead of direct API calls:

```
┌─────────────────┐
│   Orchestrator  │  → claude CLI (licensed)
└────────┬────────┘
         │ MAT-2 JSON
         ▼
┌─────────────────┐
│     Worker      │  → codex CLI (licensed)
└────────┬────────┘
         │ MAT-1 JSON
         ▼
┌─────────────────┐
│  Git Executor   │  → gemini CLI (licensed)
└─────────────────┘
```

**Benefits:**
- No API keys — each CLI uses its own subscription/license
- No duplicate billing — CLI license covers usage
- No auth management — each CLI handles its own login flow

## Core concepts

### Agents

Keys under **`agents`** are usually **roles** (`orchestrator`, `worker`, `executor`, …). The runtime also accepts **agent names** (e.g. `reviewer`, `coder`): **`AgentRouter`** merges **`agents.<role>`** first, then **`agents.<agent-name>`**, so per-agent settings override role defaults without changing every worker.

Each agent binds a semantic role to a CLI tool:

```json
{
  "agents": {
    "orchestrator": {
      "cli": "claude",
      "capabilities": ["planning", "routing", "synthesis"]
    },
    "worker": {
      "cli": "codex",
      "capabilities": ["implement", "test", "refactor", "diagnose"]
    },
    "git-executor": {
      "cli": "gemini",
      "capabilities": ["git-ops", "research"]
    }
  }
}
```

**Supported CLI tools:**
- `claude` — Claude Code CLI
- `codex` — OpenAI Codex CLI (`codex exec`, implement/test/refactor/diagnose)
- `codex-review` — Codex review-only path (`codex review`; optional for **reviewer** if you prefer Codex-only review)
- `gemini` — Google Gemini CLI
- `cursor` — Cursor editor CLI
- `aider` — Aider CLI
- `continue` — Continue CLI
- `custom` — Any CLI (requires `command` field)

### Capabilities

Capabilities describe what an agent can do:

| Capability | Description | Typical CLI |
|------------|-------------|-------------|
| `planning` | Break down complex tasks | claude |
| `routing` | Decide which agent handles what | claude |
| `synthesis` | Combine results from multiple agents | claude |
| `review` | Code review and analysis | claude, codex, codex-review |
| `implement` | Write/modify code | codex |
| `test` | Write and run tests | codex |
| `refactor` | Restructure existing code | codex |
| `diagnose` | Debug and root-cause analysis | codex |
| `git-ops` | Git operations (MAT-1) | gemini |
| `research` | Information gathering | gemini |
| `chat` | Interactive conversation | any |

### Routing

Optional explicit routing maps operation types to agents:

```json
{
  "routing": {
    "codex_ops": "worker",
    "git_ops": "git-executor",
    "planning": "orchestrator",
    "research": "git-executor"
  }
}
```

### Custom CLI tools

For tools not in the preset list:

```json
{
  "agents": {
    "worker": {
      "cli": "custom",
      "command": "/usr/local/bin/my-codex-wrapper",
      "capabilities": ["implement"],
      "flags": ["--json-mode"]
    }
  }
}
```

## Minimal example

```json
{
  "schema_version": "1.0.0",
  "agents": {
    "default": {
      "cli": "claude",
      "capabilities": ["planning", "routing", "synthesis", "implement", "review"]
    }
  }
}
```

## Full example

```json
{
  "schema_version": "1.0.0",
  "agents": {
    "orchestrator": {
      "cli": "claude",
      "capabilities": ["planning", "routing", "synthesis", "review"],
      "timeout_ms": 300000
    },
    "worker": {
      "cli": "codex",
      "capabilities": ["implement", "test", "refactor", "diagnose"],
      "flags": ["--approval-mode", "full-auto"],
      "timeout_ms": 600000
    },
    "git-executor": {
      "cli": "gemini",
      "capabilities": ["git-ops", "research"],
      "timeout_ms": 120000
    }
  },
  "routing": {
    "codex_ops": "worker",
    "git_ops": "git-executor",
    "planning": "orchestrator",
    "research": "git-executor"
  },
  "defaults": {
    "timeout_ms": 180000,
    "max_retries": 2
  }
}
```

## Validate locally

```bash
cd /path/to/multi-agent-toolkit
source .venv/bin/activate
pip install -r requirements-dev.txt
python scripts/validate_provider_config.py
```

## Integration with other MAT schemas

| Schema | Relationship |
|--------|--------------|
| **MAT-1** (git-ops) | Wire format for `git-executor` agent |
| **MAT-2** (codex) | Wire format for `worker` agent |
| **MAT-9** (repo profile) | Repository-specific paths and work-item adapters |
| **MAT-16** (this schema) | Which CLI tool handles which role |

A typical setup:
1. `~/.config/mat/agents.json` — User's agent configuration
2. `./ai-team.repo.json` — Repository-specific profile (MAT-9)
3. CLI tools authenticated — Each via its own login flow
