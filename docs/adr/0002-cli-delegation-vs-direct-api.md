# ADR 0002: CLI delegation vs direct API access

**Status:** Accepted  
**Date:** 2026-04-16  
**Tickets:** MAT-16  
**Context:** Multi-Agent Toolkit — how orchestrators invoke LLM capabilities across providers.

## Context

The toolkit coordinates work across multiple AI agents: an **orchestrator** (Claude Code), a **code worker** (Codex), and a **git/research executor** (Gemini). The question is how these agents are invoked:

**Option A: Direct API access**
- Orchestrator makes HTTP calls directly to provider APIs (Anthropic, OpenAI, Google)
- Requires API keys in environment variables
- Per-token billing for each request
- Full control over model selection, parameters, and retry logic

**Option B: CLI delegation**
- Orchestrator invokes other CLI tools (`claude`, `codex`, `gemini`)
- Each CLI manages its own authentication via existing license/subscription
- No additional per-token billing beyond existing subscriptions
- Relies on CLI tool availability and their built-in capabilities

## Decision

**CLI delegation is the primary invocation model** for the Multi-Agent Toolkit.

- Agents are invoked via their respective CLI tools, not direct API calls
- Authentication is handled by each CLI's existing login/license mechanism
- The toolkit defines **wire formats** (MAT-1, MAT-2) for structured communication, not API client code
- MAT-16 defines **agent bindings** — which CLI tool handles which role — not API key configuration

## Rationale

1. **Cost efficiency** — Teams with existing CLI subscriptions (Claude Code, Codex CLI, Gemini CLI) avoid duplicate per-token API billing. The CLI license already covers usage.

2. **Simplified authentication** — No API key management, rotation, or environment variable sprawl. Each CLI handles its own auth flow (OAuth, API key, SSO).

3. **Leverages existing tooling** — CLI tools provide features the toolkit would otherwise need to implement: context management, rate limiting, caching, interactive modes.

4. **Separation of concerns** — The toolkit focuses on **coordination contracts** (schemas, routing, state), not LLM client libraries. Each CLI is a black box that speaks the wire format.

5. **Enterprise compatibility** — Many enterprises provision AI access via managed CLI tools with SSO, audit logging, and policy controls. Direct API access may bypass these controls.

## Consequences

- **MAT-16 schema** defines agent-to-CLI bindings and capability routing, not API keys or model IDs
- **No LiteLLM/LangChain dependency** — the toolkit remains schema-first without runtime LLM client code
- **CLI availability required** — agents must have the relevant CLI tools installed and authenticated
- **Future direct-API mode** — if needed, a separate schema (or MAT-16 v2) can add optional API-direct configuration for environments without CLI access

## Agent binding model

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
│  Git Executor   │  (Gemini CLI or MCP bridge)
│   - git ops     │
│   - research    │
└─────────────────┘
```

Each arrow represents a **wire format** (MAT-1/MAT-2 JSON), not an API call. The CLI tools translate these into their native operations.

## Alternatives considered

| Alternative | Why not chosen |
|-------------|----------------|
| **Direct API access (API keys)** | Requires per-token billing separate from existing CLI subscriptions; adds API key management burden; duplicates functionality CLI tools already provide. |
| **LiteLLM/LangChain abstraction** | Adds runtime dependency and supply chain risk (see LiteLLM March 2026 incident); toolkit stays schema-first. |
| **Hybrid (CLI + API fallback)** | Complexity without clear benefit; can be added in MAT-16 v2 if CLI-only proves insufficient. |
