# MAT-100 Spike — Replace MAT-2 with Agent Client Protocol (ACP)?

**Ticket:** [#100](https://github.com/zsleavitt/multi-agent-toolkit/issues/100)  
**Date:** 2026-07-29  
**Status:** Spike complete — recommendation below  
**Related:** prior gap analysis (PR #95 context / issue #100 refs); ADR [0002](../docs/adr/0002-cli-delegation-vs-direct-api.md) (CLI delegation); MAT-2 bundle [`schemas/codex-code-exec/v1/`](../schemas/codex-code-exec/v1/)

---

## 1. Verdict (read this first)

**Recommendation: hybrid — adopt ACP as the worker transport; keep MAT governance above it.**

| Choice | Decision |
|--------|----------|
| Replace MAT-2 wholesale with ACP | **No** — ACP is a *session/prompt/tool-call transport*, not a governance contract |
| Keep MAT-2 + `codex exec` stdout forever | **No** — that path reinvents what Codex/Claude/Gemini already speak natively |
| **ACP under MAT routing** | **Yes** — MAT still owns op allowlists, idempotency, correlation, budgets, MAT-1 git boundary; adapters speak ACP instead of stuffing prompts into `codex exec` |

Concrete follow-on: prototype one worker (Codex via its ACP adapter) behind `AgentRouter`, map MAT-2 ops → ACP `session/prompt` + collect `session/update` into today's `MAT2Response` shape. Deprecate stdout-only adapters after parity.

Sketch of the MAT→ACP bridge: [`schemas/acp-spike/v1/`](../schemas/acp-spike/v1/).

---

## 2. What ACP is (and is not)

### 2.1 What ACP provides

[Agent Client Protocol](https://agentclientprotocol.com/) (ACP) is JSON-RPC 2.0 over **stdio** (primary) for *Client ↔ coding Agent*. Zed created it; editors and CLIs adopted it. MAT-relevant agents on the [ACP agents list](https://agentclientprotocol.com/get-started/agents) include **Codex CLI** (via Zed's adapter), **Gemini CLI**, **Claude Agent** (via adapter), Cursor, Copilot CLI, and many others.

Typical message flow ([overview](https://agentclientprotocol.com/protocol/v2/overview), [prompt lifecycle](https://agentclientprotocol.com/protocol/v2/prompt-lifecycle)):

1. **`initialize`** — protocol version + capability negotiation  
2. **`auth/login`** (optional) — if the agent advertises auth methods  
3. **`session/new`** — create a session with absolute **`cwd`**, optional MCP server configs  
4. **`session/prompt`** — send multimodal content; agent **acks immediately** (`result: {}`); work continues asynchronously  
5. **`session/update` notifications** — streaming: user/agent messages, plans, **tool_call_update** / chunks, **usage_update**, **state_update** (`running` → `idle` + `stopReason`)  
6. **`session/request_permission`** — agent asks client to approve tool/command actions  
7. **`session/cancel` / `session/close` / `session/resume`** — interrupt, teardown, reconnect (+ optional history replay)

ACP also streams **usage/cost** (`usage_update`: token `used`/`size`, optional `cost.amount`/`currency`) and supports MCP servers attached at session creation — aligning with ADR 0004's future direction of passing tools into workers without inventing another IPC.

### 2.2 What ACP is not

ACP does **not** define:

- Named task ops (`implement` / `test` / `review`) with deny-by-default allowlists  
- Orchestrator-level **idempotency keys** or safe replay of whole tasks  
- MAT **error codes** (`POLICY_BLOCKED`, `SANDBOX_ERROR`, `TEST_FAILED`, …)  
- Cross-vendor **routing policy** (which CLI for which role)  
- **Git** allowlisting (that remains MAT-1 / MCP git server)  
- Crew / swarm / hive consensus semantics  

ACP is the *pipe and session UX*; MAT is the *policy and multi-agent graph*.

---

## 3. MAT-2 today (baseline)

MAT-2 (`schemas/codex-code-exec/v1/`) is a **request/response envelope**:

| Field | Role |
|-------|------|
| `schema_version` | Wire evolution (`1.0.0` … `1.2.0`) |
| `correlation_id` | End-to-end trace |
| `idempotency_key` | Safe retries; `replay: true` on response |
| `repo_root` | Explicit workspace root |
| `timeout_ms` | Wall-clock budget (MAT-14) |
| `session` `{session_id, turn}` | Optional multi-turn handle |
| `op` | Allowlisted: `codex.implement` / `test` / `refactor` / `diagnose` / `review` |
| `params` | Op-specific structured inputs |

Responses are success (`ok`, `result`, `replay`) or failure (`error.code` from a fixed enum). Recommended result shapes include `changed_files`, test exit codes, diagnose/review findings.

**Runtime reality:** `AgentRouter` → CLI adapters (e.g. `CodexAdapter` → `codex exec --full-auto <prompt>`) → parse **stdout** into `MAT2Response`. The MAT-2 JSON is largely an *orchestrator contract*; the CLI boundary is still free-form text, not structured tool-call events. That is the gap ACP closes.

---

## 4. Conceptual mapping: MAT-2 ↔ ACP

| MAT-2 concept | ACP analogue | Fit |
|---------------|--------------|-----|
| `repo_root` | `session/new` → `cwd` (absolute) | Strong |
| `session.session_id` | ACP `sessionId` from `session/new` / `session/resume` | Strong |
| `session.turn` (client monotonic) | Implicit: each `session/prompt` is a new user turn; no client turn counter in ACP | Partial — MAT can keep `turn` locally |
| One-shot task | `session/new` → one `session/prompt` → wait for `idle` | Strong |
| Multi-turn resume | `session/resume` (+ optional `replayFrom`) | Stronger than MAT-2's thin turn model |
| Streaming progress | *(none in MAT-2 wire)* | ACP wins (`session/update`) |
| Tool / file edits visibility | Implied by final `result.changed_files` (if adapter fills it) | ACP wins (`tool_call_update`, kinds: read/edit/execute/…) |
| Timeout | Client-side `timeout_ms` on subprocess | Partial — ACP has cancel + stop reasons (`max_tokens`, `max_turn_requests`); wall-clock still client |
| Structured final result | Success/failure envelope | Partial — ACP ends with `idle` + messages/tool trail; **MAT must synthesize** `result_*` |
| `idempotency_key` / `replay` | None | **None** — keep in MAT |
| `correlation_id` | None (use `_meta` or client logs) | Partial — put in `_meta` / OTel |
| Op allowlist | None | **None** — keep in MAT |
| Permission for tools | Agent → `session/request_permission` | Strong — better HITL than silent `--full-auto` |

---

## 5. Feature parity table

Legend: **Native** = ACP covers it; **Partial** = possible with mapping/client work; **None** = MAT must keep owning it.

| MAT-2 feature | ACP coverage | Notes |
|---------------|--------------|-------|
| `codex.implement` | **Partial** | Prompt text (+ scope/acceptance in prompt or `_meta`); edits via tool-call events, not `result.changed_files` |
| `codex.test` | **Partial** | No `test_profile` enum; map profile→fixed argv in MAT, ask agent to run *or* run tests outside ACP; tool `execute` events approximate |
| `codex.refactor` | **Partial** | Same as implement; scope_paths enforced by MAT policy / permission denials |
| `codex.diagnose` | **Partial** | Prompt + readonly intent; structured `result_diagnose` must be parsed from final agent message or `_meta` convention |
| `codex.review` | **Partial** | Same; `findings[]` not an ACP type — synthesize from agent output or require JSON-in-message convention |
| Retry / idempotency | **None** | JSON-RPC ids ≠ task idempotency; MAT `idempotency_key` + result cache stay |
| `timeout_ms` | **Partial** | Client timer + `session/cancel`; ACP stop reasons for model limits, not wall-clock |
| Structured results | **Partial** | Stream is structured; **final MAT envelope** is a MAT synthesizer job |
| Session / turn | **Native** (session) / **Partial** (turn) | Prefer ACP `sessionId`; keep MAT turn for orchestrator bookkeeping if useful |
| Error codes | **Partial** | JSON-RPC errors + `stopReason`; map to MAT codes in adapter |
| Budget / cost | **Partial** | `usage_update` feeds MAT-98 budgets; enforcement stays in MAT |
| Op allowlisting | **None** | Manifest + router |
| High-risk ops | **Partial** | Use ACP permissions + MAT policy before `session/prompt` |
| Git staging/commit | **Out of scope** | Still MAT-1 (or MCP git server, MAT-101) — never ACP “free shell” |

---

## 6. What MAT-2 has with **no** ACP equivalent (today)

These must remain a **MAT layer above ACP** (or be consciously dropped):

1. **`idempotency_key` + `replay`** — safe orchestrator retries across process restarts  
2. **Deny-by-default `op` allowlist** (`manifest.json`) — ACP accepts arbitrary prompts  
3. **MAT-specific `error.code` taxonomy** — policy/sandbox/test-failed semantics for crews/hives  
4. **Op-typed params & recommended result schemas** (`result_review.findings`, `test_profile`, …)  
5. **Budget *enforcement*** (MAT-98) — ACP reports usage; MAT decides halt/downgrade  
6. **Correlation / schema_version** as first-class wire fields — use `_meta` + keep MAT envelope for skills/Gumloop/HTTP prototypes  
7. **Multi-agent graph** — crews, swarms, hives, consensus — orthogonal to ACP  

Also **do not drop**: MAT-1 git boundary. ACP agents can edit files and run commands; MAT still routes *git policy* through the allowlisted executor.

---

## 7. Migration cost estimate

### 7.1 What would break / change

| Area | Impact | Effort |
|------|--------|--------|
| `CodexAdapter` / `ClaudeAdapter` / `GeminiAdapter` | New ACP stdio client (initialize → session → prompt → drain updates) | M — one shared `AcpClient`, per-CLI spawn argv |
| `AgentRouter` / skills | Keep MAT-2 request API; swap invoke path | S–M |
| Result synthesis | Build `changed_files` / review findings from tool-call + message stream | M — heuristics + optional JSON convention in prompts |
| Permissions | Auto-approve policy for non-interactive MAT runs, or HITL bridge | M — product choice |
| Tests / smoke | ACP integration fixtures; mock JSON-RPC | M |
| Docs / ADRs | Update 0002 diagram: MAT-2 *governance* → ACP *transport* → CLI | S |
| Gumloop / HTTP prototypes | Unchanged if they still POST MAT-2 to a bridge that speaks ACP underneath | S |

### 7.2 What could be dropped (later)

- Prompt-stuffing MAT-2 JSON into `codex exec` argv and scraping stdout  
- Duplicative thin “session.turn” if orchestrator adopts ACP `sessionId` as source of truth  
- Ad-hoc “parse last JSON blob from stdout” patterns in adapters  

### 7.3 What must remain above ACP

- MAT-2 (or successor) **governance envelope**: op, params validation, idempotency, correlation, timeout policy, error taxonomy  
- MAT-16 routing / agent bindings  
- MAT-1 / MCP git  
- Crew/swarm/hive + resilience/budgets/OTel  

### 7.4 Rough sequencing

1. **Spike prototype** (this ticket’s follow-on): Codex-only ACP adapter behind feature flag; map `codex.implement` only.  
2. **Parity**: synthesize `MAT2Response` for all five ops; smoke + eval harness trajectories assert tool-call events.  
3. **Default**: ACP path on; keep exec fallback one release.  
4. **Schema**: either keep MAT-2 as-is (envelope only) or publish `mat-over-acp@v1` documenting `_meta` conventions — avoid breaking Gumloop examples until a version bump.

**Order-of-magnitude:** ~1–2 weeks for a trustworthy Codex prototype; ~1 month for multi-CLI parity + permission policy + docs. Not a “delete MAT-2 schemas” rewrite.

---

## 8. Options and recommendation

### A — Adopt ACP as transport (keep MAT governance) — **recommended**

Matches gap-analysis Option A. Preserves multi-vendor CLI orchestration and schema-first policy; stops reinventing session/tool streaming. Aligns with ADR 0002 (CLI delegation) — ACP is *how modern CLIs want to be driven*, not a pivot to HTTP APIs.

### B — Keep MAT-2 + stdout exec as-is

Lowest short-term churn; highest long-term reinvention debt. Continues to miss structured tool-call telemetry that evals (MAT-99) and OTel want.

### C — Replace MAT-2 entirely with raw ACP

Loses deny-by-default ops, idempotency, and typed results unless reimplemented ad hoc in prompts. Breaks skills and external MAT-2 consumers. **Reject.**

### Explicit recommendation

**Hybrid (A):** Keep the MAT-2 *envelope* (or a thin evolution of it) as the orchestrator↔runtime contract; implement **ACP as the adapter transport** to worker CLIs. Document op→prompt templates and result synthesizers. Do **not** pretend ACP alone is a drop-in MAT-2.

---

## 9. Follow-on implementation checklist

- [ ] `mat_runtime/adapters/acp_client.py` — stdio JSON-RPC NDJSON client  
- [ ] Feature-flag `MAT_WORKER_TRANSPORT=acp|exec`  
- [ ] Map ops → prompt templates (reuse agent system prompts)  
- [ ] Permission policy: `auto_approve` vs `deny` vs HITL  
- [ ] Synthesize `MAT2Response` from idle + tool trail  
- [ ] Feed `usage_update` into MAT-98 budget tracker  
- [ ] Eval trajectory scorer: “worker emitted edit/execute tool calls”  
- [ ] ADR addendum to 0002 or new ADR “ACP transport under MAT-2”  

---

## 10. Sources

- [ACP overview (v2)](https://agentclientprotocol.com/protocol/v2/overview)  
- [ACP transports](https://agentclientprotocol.com/protocol/v2/transports)  
- [ACP session setup](https://agentclientprotocol.com/protocol/v2/session-setup)  
- [ACP prompt lifecycle](https://agentclientprotocol.com/protocol/v2/prompt-lifecycle)  
- [ACP tool calls](https://agentclientprotocol.com/protocol/v2/tool-calls)  
- [ACP agents list](https://agentclientprotocol.com/get-started/agents)  
- [Zed ACP](https://zed.dev/acp)  
- MAT-2: `schemas/codex-code-exec/v1/`  
- ADR 0002: CLI delegation vs direct API  
- Prior gap analysis (PR #95 context): Tier 2 item “Evaluate replacing MAT-2 with ACP”
