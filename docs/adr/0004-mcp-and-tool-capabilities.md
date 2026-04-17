# ADR 0004: MCP and tool capabilities architecture

**Status:** Accepted  
**Date:** 2026-04-17  
**Tickets:** MAT-32, MAT-33, MAT-34, MAT-35  
**Context:** Multi-Agent Toolkit — how MCPs and tool capabilities are managed across agents.

## Context

The toolkit coordinates work across agents with different capabilities:

- **Orchestrator (Claude Code)**: Has access to MCPs (Notion, Slack, GitHub, etc.) via user configuration
- **Workers (Codex, etc.)**: May have limited or no MCP access; focused on code execution
- **Executors (Gemini, etc.)**: Specialized for git ops and research

Two questions arise:

1. **MCP availability**: Should workers inherit MCPs from the orchestrator, or should integration tasks stay at the orchestrator level?

2. **Tool restrictions**: Should different agents have different tool permissions? (e.g., reviewer agent shouldn't have edit capabilities)

## Decision

### Part 1: MCP stays at orchestrator level (v1)

**Integration-dependent operations (ticket creation, Slack, external APIs) run in the orchestrator context**, not delegated to workers.

- The `/ticket` skill invokes MCPs directly in Claude Code
- Workers signal *need* for tickets; orchestrator creates them
- Workers remain focused on code tasks (implement, test, diagnose, review)

Future v2 consideration: MCP inheritance or shared MCP configuration across agents.

### Part 2: Agent capability boundaries

**Agent definitions (MAT-17) should declare tool restrictions** as part of the agent's behavioral contract:

| Agent | Allowed tools | Restricted |
|-------|---------------|------------|
| orchestrator | All (planning, routing, MCPs) | — |
| coder | Read, Write, Edit, Bash | MCPs (integration tasks) |
| tester | Read, Write, Edit, Bash | — |
| reviewer | Read, Grep, Glob | Edit, Write (read-only analysis) |
| researcher | Read, WebSearch, WebFetch | Edit, Write |

These restrictions are **advisory in v1** (documented in agent definitions) and **enforced in v2** (runtime validates tool calls against agent capabilities).

## Rationale

### Why keep MCPs at orchestrator level:

1. **Configuration complexity** — Each CLI tool (claude, codex, gemini) has its own MCP/extension configuration. There's no standard inheritance mechanism today.

2. **Separation of concerns** — Integration tasks (tickets, notifications, external APIs) are coordination activities that naturally fit the orchestrator role.

3. **Security boundary** — Limiting which agents can access external systems reduces blast radius of compromised or misbehaving workers.

4. **Simpler v1** — Get the toolkit working without solving cross-agent MCP synchronization.

### Why declare tool restrictions:

1. **Principle of least privilege** — Reviewer agents analyzing code shouldn't accidentally modify it.

2. **Clearer contracts** — Agent definitions explicitly state what each agent can and cannot do.

3. **Future enforcement** — Paves the way for runtime tool call validation.

4. **Trust boundaries** — When delegating to external workers (Codex), limiting their capabilities reduces risk.

## Consequences

- **`/ticket` skill** runs in orchestrator, uses Notion MCP directly
- **Workers** cannot create tickets directly; they return structured responses that the orchestrator can act on
- **Agent definitions** (MAT-17) should document `capabilities` and `restrictions` fields
- **Setup wizard** (MAT-35) configures ticket provider for orchestrator, not for all agents
- **Future MAT-17 v2** could add `allowed_tools` / `denied_tools` fields with runtime enforcement

## Implementation approach

```
┌─────────────────────────────────────────────────────────────┐
│  Claude Code (orchestrator)                                 │
│  ├── MCPs: Notion, Slack, GitHub, etc.                      │
│  ├── Skills: /ticket, /plan, /develop                       │
│  └── Full tool access                                       │
└──────────────────────┬──────────────────────────────────────┘
                       │ MAT-2 JSON (no MCP calls)
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  Worker (Codex)                                             │
│  ├── No MCP access                                          │
│  ├── Tools: Read, Write, Edit, Bash                         │
│  └── Returns structured results → orchestrator handles      │
└─────────────────────────────────────────────────────────────┘
```

## Alternatives considered

| Alternative | Why not chosen (for v1) |
|-------------|-------------------------|
| **MCP inheritance** — Workers automatically get orchestrator's MCPs | No standard mechanism; adds complexity; conflates code work with integration work. Consider for v2. |
| **Shared MCP config** — Setup wizard configures MCPs for all agents | Requires understanding each CLI's config format; maintenance burden. Consider for v2. |
| **No tool restrictions** — All agents can use all tools | Violates least privilege; reviewer shouldn't edit; increases risk surface. |

## Future work (v2)

1. **MAT-17 v2**: Add `allowed_tools` / `denied_tools` fields to agent schema
2. **Runtime enforcement**: Router validates tool calls against agent capabilities
3. **MCP forwarding**: Orchestrator could proxy MCP calls for workers (complex but enables full autonomy)
4. **Setup wizard MCP sync**: Detect orchestrator MCPs and offer to configure for other agents
