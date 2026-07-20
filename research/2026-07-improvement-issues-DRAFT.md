# Draft GitHub issues — MAT improvements (2026-07)

**Status: DRAFT reference.** These issues were created in the tracker on 2026-07-20 (see the `roadmap-2026-07`-related PR/issues). This file is the source-of-truth text they were generated from.

Each issue below maps to a created GitHub issue. MAT-XX numbers are conceptual placeholders — see the actual issue numbers in the repo tracker.

---

## Tier 1 — Operational gaps (do regardless of strategy)

### ISSUE 1 — Emit OpenTelemetry GenAI spans from AgentRouter
**Problem.** MAT has no tracing. There is no way to see what the orchestrator routed, how long each CLI call took, how many tokens it burned, or where a run failed. This blocks debugging, cost visibility, and eval trace capture.

**Proposal.** Instrument `mat_runtime/router.py` (`AgentRouter.invoke`) to emit OpenTelemetry spans following the **GenAI semantic conventions** (`gen_ai.*`): one root span per task, child spans per CLI invocation (orchestrator / Codex / Gemini) with attributes for `gen_ai.request.model`, token usage, latency, and error status. Export via OTLP so any backend (Langfuse / Phoenix / Datadog) can ingest.

**Acceptance criteria.**
- Root + child spans emitted for a `python -m mat_runtime invoke` run.
- `gen_ai.*` attributes populated where the CLI surfaces them; gracefully degraded where it doesn't.
- SemConv version pinned in config (attributes are still "Development" stability — expect churn).
- Docs section + example trace.

---

### ISSUE 2 — Add cost + resilience controls to CLI invocations
**Problem.** MAT shells out to CLIs with only `timeout_ms`. No token/cost budget, no retries, no circuit breaker. A runaway loop or a flaky CLI has no guardrail.

**Proposal.**
- Extend the MAT-4 orchestrator-state schema with a per-task and per-session **token + cost budget** that can halt or downgrade a run when exceeded.
- Wrap every CLI call with: timeout (exists), **bounded exponential-backoff retries** with idempotency, and a **circuit breaker** that trips on repeated failures / spend-rate spikes.

**Acceptance criteria.**
- Budget fields added to `schemas/orchestrator-state/v1/` + validator updated.
- Retry/breaker wrapper around adapter calls with unit tests (simulated failures/timeouts).
- Run halts with a clear state transition when budget exceeded.

---

### ISSUE 3 — Build an agent-quality eval harness with CI gate
**Problem.** pytest covers the framework's Python, but there is **no evaluation of agent output quality or routing correctness**. Nothing catches a silent regression when a prompt, model, or routing rule changes.

**Proposal.** Add an eval harness: a versioned **golden-task set** (start with 20–50 tasks mined from real failures), scored by deterministic checks + LLM-as-judge, including **trajectory checks** (did the orchestrator route to the correct worker? did the git executor run *only* allowlisted ops?). Wire into CI to fail the build on regression.

**Acceptance criteria.**
- `evals/` dir with golden tasks + expected outcomes.
- Runner producing pass/fail + score deltas; consumes OTel traces from Issue 1 where available.
- CI job that blocks merge on metric drop beyond threshold.

---

## Tier 2 — Stop reinventing standardized wire formats

### ISSUE 4 — Spike: replace MAT-2 with the Agent Client Protocol (ACP)
**Problem.** MAT-2 is a bespoke JSON contract for "a client drives a coding agent." That interaction now has an adopted standard — **ACP** (JSON-RPC over stdio) — and **the CLIs MAT wraps (Claude Code, Codex CLI, Gemini CLI) already implement it.** MAT-2 is effectively a private re-implementation of ACP's session/turn/tool-call model, and MAT currently parses CLI stdout instead of receiving structured tool-call events.

**Proposal (spike first, then decide).** Prototype driving one worker (Codex) through its native ACP endpoint instead of MAT-2. Compare: structured tool-call reporting, session/turn handling, maintenance burden, feature parity with `implement/test/refactor/diagnose/review`.

**Acceptance criteria.**
- Spike doc: what ACP gives for free, what MAT-2 features have no ACP equivalent, migration cost.
- Recommendation: adopt ACP as transport (keep MAT's routing/governance above it), keep MAT-2, or hybrid.

**Refs.** https://agentclientprotocol.com/get-started/agents · https://zed.dev/acp

---

### ISSUE 5 — Expose the MAT-1 git executor as an MCP server
**Problem.** MAT-1 is a deny-by-default, manifest-allowlisted set of git/CLI operations with no shell — i.e., a permissioned tool server. That is the canonical **MCP** use case, but MAT-1 is a private format usable only by MAT.

**Proposal.** Wrap the git executor as an **MCP server** exposing the allowlisted ops as MCP tools with the manifest as the permission boundary. Any MCP client (not just MAT) could then use it, and MAT's orchestrator talks to it over a standard transport.

**Acceptance criteria.**
- MCP server exposing `git.add/commit/diff/branch/...` per the current allowlist.
- Manifest allowlist enforced as tool-level permissioning; deny-by-default preserved.
- MAT-1 kept as an internal contract or mapped onto the MCP tool schema (document the choice).

---

### ISSUE 6 — Align HITL with MCP Elicitation + durable interrupt/resume
**Problem.** MAT-6 (Asana approval on `blocked_hitl`) is a fire-and-forget external callback with approve/callback only. The 2026 standard is durable **interrupt/resume** on checkpointed state with approve/reject/**edit**/respond semantics; MCP also standardizes human input via **Elicitation**.

**Proposal.** Add `edit` and `respond` decision types alongside approve/reject. Tie an approval to a **resumable checkpoint** so a `blocked_hitl` item pauses and later resumes from persisted state rather than re-running. Model the request/response shape on MCP Elicitation; keep Asana as one backend.

**Acceptance criteria.**
- MAT-6 schema gains edit/respond; validator updated.
- A blocked run can be resumed (not restarted) after human input, with a test.

---

## Tier 3 — Reduce reinvention debt vs. the native substrate

### ISSUE 7 — Pluggable checkpointer/memory interface behind MAT-4
**Problem.** `orchestrator.state.json` is a flat file. Production norm is a **checkpointer** (thread state, resume, time-travel) plus an optional **long-term store** with vector recall.

**Proposal.** Define a checkpointer interface behind the MAT-4 schema with a JSON backend today and pluggable SQLite/Redis/Postgres later; optionally a separate long-term store interface (vector search) for cross-run memory. Keep the contract stable, swap the backend.

**Acceptance criteria.**
- Interface + JSON implementation; one alternative backend (SQLite) to prove pluggability.
- Resume-from-checkpoint path with a test.

---

### ISSUE 8 — Reconcile MAT with native Claude Code features
**Problem.** Claude Code now ships **native subagents** (markdown+frontmatter — same format as MAT agents), **native worktree isolation** (`isolation: worktree`, v2.1.49), and experimental **Agent Teams** (≈ MAT's hive). MAT duplicates several of these.

**Proposal.** Audit MAT's agents/hive/worktree layers against native equivalents. Document where MAT should **defer to native** (drop the redundant worktree config; treat native subagents as the agent runtime) vs. where MAT adds real value (multi-vendor routing, consensus, governance). Update `agents/README.md` and relevant ADRs.

**Acceptance criteria.**
- Mapping table MAT-concept → native-equivalent → keep/defer/drop decision.
- Redundant config removed or explicitly justified.

**Refs.** https://code.claude.com/docs/en/worktrees · https://claudefa.st/blog/guide/agents/agent-teams

---

### ISSUE 9 — (Optional) Express agents as A2A Agent Cards
**Problem.** MAT's agent definitions + crew/swarm/hive registries reinvent capability advertising. **A2A Agent Cards** are the standard machine-readable capability/identity/endpoint documents.

**Proposal.** Only if cross-host / cross-vendor discovery becomes a real goal: emit an A2A Agent Card per MAT agent so discovery/routing is portable and interoperable. Otherwise defer.

**Acceptance criteria.**
- Decision recorded (do now / defer) with the triggering requirement.
- If done: Agent Card generated from MAT-17 agent definitions.

---

## Tier 4 — Positioning & risk

### ISSUE 10 — ADR: strategic positioning + vendor-CLI-churn hedge
**Problem.** MAT's defensible surface has narrowed to multi-vendor CLI orchestration + schema-first governance + consensus. Meanwhile vendor CLIs churn — Google ended free Gemini CLI access (Jun 18 2026), directly threatening MAT's git-executor leg.

**Proposal.** Write an ADR choosing a direction (A: adopt standards + keep governance layer; B: double down as multi-vendor governance orchestrator; C: narrow to a Claude Code plugin). Include a **pluggable worker-CLI** hedge so losing any single vendor CLI (e.g., Gemini) is not fatal.

**Acceptance criteria.**
- ADR committed under `docs/adr/` with decision + consequences.
- Follow-up issues spawned from the chosen path.

---

### ISSUE 11 — Disambiguate "swarms" naming; foreground consensus voting
**Problem.** "Swarm" collides with OpenAI's deprecated Swarm project, causing confusion. MAT's actual differentiator in that layer is **first-class consensus strategies** (majority-vote/first-complete/return-all), which is under-marketed.

**Proposal.** Rename or clearly disambiguate the concept, and reframe docs around consensus voting as the value (not parallel dispatch, which is commodity).

**Acceptance criteria.**
- Naming decision + doc updates.
- Consensus strategies documented as the headline feature of that layer.
