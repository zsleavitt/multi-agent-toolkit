# MAT-16 — Provider configuration schema (`v1`)

Versioned JSON Schema for **model-agnostic LLM provider configuration**. This schema enables orchestrators and agents to work with any LLM provider without hardcoding vendor-specific details.

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
| `provider-config.schema.json` | Main schema for provider configuration documents. |
| `examples/` | Valid / invalid fixtures for CI. |

## Core concepts

### Providers

Each provider entry configures access to an LLM API:

```json
{
  "providers": {
    "anthropic": {
      "type": "anthropic",
      "auth_env": "ANTHROPIC_API_KEY"
    },
    "openai-enterprise": {
      "type": "openai",
      "auth_env": "OPENAI_API_KEY",
      "org_id_env": "OPENAI_ORG_ID",
      "api_base": "https://api.enterprise.openai.com/v1"
    }
  }
}
```

**Supported provider types:**
- `anthropic` — Anthropic API (Claude models)
- `openai` — OpenAI API (GPT, Codex models)
- `google` — Google AI / Vertex AI (Gemini models)
- `azure` — Azure OpenAI Service
- `bedrock` — AWS Bedrock
- `ollama` — Local Ollama instance
- `openrouter` — OpenRouter proxy
- `custom` — Any OpenAI-compatible API (requires `api_base`)

### Model aliases

Semantic names that decouple orchestration logic from specific models:

```json
{
  "model_aliases": {
    "orchestrator": {
      "provider": "anthropic",
      "model": "claude-sonnet-4-20250514",
      "max_tokens": 8192,
      "fallback": [
        { "provider": "openai", "model": "gpt-4o" }
      ]
    },
    "worker": {
      "provider": "openai",
      "model": "codex-2",
      "temperature": 0.2
    },
    "fast": {
      "provider": "anthropic",
      "model": "claude-haiku-4-20250514"
    }
  }
}
```

**Common alias patterns:**
- `orchestrator` — Primary planning/routing model (high capability)
- `worker` — Code execution/implementation model
- `reviewer` — Code review/analysis model
- `fast` — Quick responses, lower latency
- `cheap` — Cost-optimized for bulk operations

### Fallback chains

When a primary model/provider is unavailable, fallbacks provide resilience:

```json
{
  "fallback": [
    { "provider": "openai", "model": "gpt-4o" },
    { "provider": "ollama-local", "model": "llama3:70b" }
  ]
}
```

### Budgets

Cost and usage guardrails enforced by the executor:

```json
{
  "budgets": {
    "daily_token_limit": 5000000,
    "daily_cost_limit_cents": 5000,
    "session_token_limit": 500000
  }
}
```

## Security

**Critical: Never store API keys in config files.**

- `auth_env` references an environment variable name, not the key itself
- `org_id_env` similarly references an env var for organization IDs
- Executors read these env vars at runtime
- Config files can be safely committed to version control

### Recommended env var naming

| Provider | API Key Env Var | Org ID Env Var |
|----------|-----------------|----------------|
| Anthropic | `ANTHROPIC_API_KEY` | — |
| OpenAI | `OPENAI_API_KEY` | `OPENAI_ORG_ID` |
| Google | `GOOGLE_AI_API_KEY` | — |
| Azure | `AZURE_OPENAI_API_KEY` | — |
| Bedrock | `AWS_ACCESS_KEY_ID` | — |

## Validate locally

```bash
cd /path/to/multi-agent-toolkit
source .venv/bin/activate
pip install -r requirements-dev.txt
python scripts/validate_provider_config.py
```

## Integration with MAT-9 repo profiles

Provider config is **separate** from repo profiles (`ai-team.repo.json`):

- **Provider config** — Which LLM providers/models to use (can be shared across repos)
- **Repo profile** — Repository identity, paths, work-item adapters (per-repo)

A typical setup:
1. `~/.config/mat/providers.json` — User's provider configuration
2. `./ai-team.repo.json` — Repository-specific profile
3. Environment variables — Actual API credentials
