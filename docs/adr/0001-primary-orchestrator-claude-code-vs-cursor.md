# ADR 0001: Primary orchestrator — Claude Code vs Cursor

**Status:** Accepted  
**Date:** 2026-04-15  
**Tickets:** MAT-8  
**Context:** Multi-Agent Toolkit — hierarchical orchestration (Claude Code ↔ Codex ↔ Gemini-style executors).

## Context

This repository defines **portable JSON contracts** and conventions for a three-role loop: an **orchestrator** plans and routes work; an **implementation worker** applies scoped code changes; a **git/CLI executor** runs deny-by-default, allowlisted operations with no arbitrary shell in the git bridge.

Teams may use **Cursor**, **Claude Code**, **IDE agents**, or custom runners at different seats. The question is which environment is the **normative orchestrator** for toolkit semantics (schemas, handoffs, validation scripts, and future state/HITL adapters).

## Decision

**Claude Code is the primary orchestrator** for toolkit design and documentation.

- **Planning, decomposition, routing, and synthesis** of multi-step work are specified for Claude Code as the session that owns the loop, tool policy, and delegation boundaries described in `research/multi-agent-research.md` and `CLAUDE.md`.
- **Cursor** (and similar editors) remain **first-class surfaces** for humans and agents to edit the repo, run validators, and optionally host auxiliary sessions. They are **not** the authority for wire-format or role boundaries unless explicitly documented as an alternative profile (future MAT-9 “repo profile” work).

## Rationale

1. **Single source of truth for orchestration semantics** — One primary orchestrator avoids ambiguous defaults (for example, whether the editor session or the headless session owns `correlation_id` chains and idempotency).
2. **Alignment with MAT-1/MAT-2 contracts** — Requests are emitted by the orchestrator to external executors; Claude Code’s tool/MCP model maps cleanly to “validate JSON → call executor → validate response.”
3. **Security posture** — The architecture explicitly keeps **git off the orchestrator**; Claude Code’s role split matches that boundary. Cursor can still attach to the same repo; the **contract** is orchestrator-agnostic JSON, but **examples and defaults** assume Claude Code.
4. **Research and Anthropic ecosystem fit** — The research note centers Claude-orchestrated patterns (subagents, compaction, `CLAUDE.md`); standardizing on Claude Code reduces drift between research, schemas, and handoff docs.

## Consequences

- **Documentation and examples** default to “Claude Code emits this request JSON.”
- **IDE workflows** should treat Claude Code (or a declared alternate orchestrator in a repo profile) as the component that **issues** MAT-1/MAT-2 payloads; editors consume artifacts and run local scripts.
- **Revisit** this ADR if MAT-9 introduces a machine-readable **orchestrator profile** field that allows multiple normative modes without contradicting schemas.

## Alternatives considered

| Alternative | Why not chosen |
|-------------|----------------|
| **Cursor as primary orchestrator** | Strong product for editing and inline agents, but toolkit contracts are headless/JSON-first; picking Cursor would couple examples to a specific editor release cadence. |
| **No primary (fully neutral)** | Maximally portable but pushes every doc and script to duplicate orchestration guidance; teams would infer incompatible defaults. |
| **LangGraph (or other framework) as primary** | Valid for some deployments; this repo stays **schema-first** and lightweight. Framework-specific ADRs can be added later if needed. |
