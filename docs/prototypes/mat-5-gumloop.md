# MAT-5 — Gumloop workflow prototype

**Goal:** Show how [Gumloop](https://www.gumloop.com/) can orchestrate the same **MAT-1 / MAT-2** JSON contracts this repo defines, without adding a new schema bundle. Gumloop stays the visual runner; your bridge (MCP, microservice, or Gumloop **HTTP** nodes) validates and forwards payloads.

**Gumloop API (reference):** `POST https://api.gumloop.com/api/v1/start_pipeline` with Bearer auth. See Gumloop docs: [Start flow run](https://docs.gumloop.com/api-reference/running-an-automation/start-automation), [Authentication](https://docs.gumloop.com/api-reference/authentication).

## Suggested flow topology (prototype)

1. **Trigger** — Gumloop Webhook or schedule; receives `repo_root`, ticket id, or a blob URL to an `ai-team.repo` profile (MAT-9).
2. **Plan (Claude Code)** — Human or separate Claude session produces a short plan (outside Gumloop, or via an LLM node). Optional: write MAT-4 `orchestrator.state.json` checkpoint paths.
3. **Code worker (MAT-2)** — **HTTP Request** node `POST` to your executor with a body matching `schemas/codex-code-exec/v1/request.schema.json` (e.g. `codex.implement`). Executor returns MAT-2 response JSON.
4. **Git (MAT-1)** — Chained **HTTP Request** nodes for `git.add` → `git.commit` → `git.push` (or your policy subset), each body matching `schemas/gemini-git-ops/v1/request.schema.json`.
5. **HITL (MAT-6)** — If queue status is `blocked_hitl`, Gumloop **Wait** / **Human approval** / Asana node; callback payload matches `schemas/hitl-asana-approval/v1/callback.schema.json` when wired to your queue bridge.

Keep **`correlation_id`** stable across Gumloop run segments so logs and MAT-4 queue rows join cleanly.

## Input node naming (convention)

Use Gumloop **Input** node `input_name` values aligned with `examples/gumloop/input-names.conventions.json` so orchestration code and docs stay consistent. All `pipeline_inputs[].value` entries are strings (stringify JSON for nested MAT request bodies).

## Runnable stub

- Example API body: `examples/gumloop/start-pipeline.request.example.json`
- Optional CLI (stdlib only): `scripts/gumloop_start_pipeline.py` — reads `GUMLOOP_API_KEY`, posts `start_pipeline`, prints `run_id` / `url`.

## Validation

Run **`python scripts/validate_gumloop_examples.py`** after `pip install -r requirements-dev.txt`. It checks that `examples/gumloop/*.json` is well-formed and that embedded **`mat2_request_json`** in `start-pipeline.request.example.json` validates against MAT-2 **`request.schema.json`**.

## Security

- Never commit API keys or `saved_item_id` values; use Gumloop workspace secrets and env vars in CI.
- MAT-1 / MAT-2 requests always carry explicit **`repo_root`** (absolute); Gumloop should not imply cwd.

## Out of scope for this prototype

- Official Gumloop canvas export (binary/UI state) — version in your Gumloop workspace.
- New MAT-* JSON Schemas for Gumloop-specific types — use HTTP + existing bundles only.
