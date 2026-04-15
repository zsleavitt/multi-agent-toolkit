# MAT-9 — Portable repo profile + work-item adapter (`v1`)

JSON Schema for **`ai-team.repo.json`** (and equivalently **`ai-team.repo.yaml`** after parsing to the same object shape). The profile carries **identity**, **repo-relative paths**, and a **single work-item adapter** so orchestration does not depend on hardcoded org URLs or implicit cwd.

## Schema identity

- Uses **Draft 2020-12** with **only** `#/$defs/...` fragment references (same convention as MAT-1 / MAT-2).
- **`manifest.json`** indexes the bundle and lists canonical filenames; it is not a JSON Schema instance.

## Repo config (`config/schema-registry.json`)

| Field | Purpose |
|-------|---------|
| `schema_bundles["ai-team-repo-profile@v1"].root_relative` | Directory containing `manifest.json`, `repo-profile.schema.json`, and `examples/`. |

Override the bundle directory without editing config:

```bash
export MAT_AI_TEAM_REPO_PROFILE_V1=/absolute/path/to/schemas/ai-team-repo-profile/v1
python scripts/validate_ai_team_repo_profile.py
```

## Work-item adapters (`work_item_source`)

| `adapter` | Block | Purpose |
|-----------|--------|---------|
| `none` | — | No external tracker; orchestrator uses local context only. |
| `linear` | `linear` | `team_id` plus optional `api_base_url` (https) for enterprise / self-hosted. |
| `jira` | `jira` | `site_host` (hostname only) + `project_key` — no `https://` prefix on host. |
| `github_issues` | `github_issues` | `owner` + `repo` — not a full GitHub URL. |
| `file` | `file` | Repo-relative `path` to a backlog file (format is consumer-defined). |

## Portable paths and `repo_root`

- **`repo.path_overrides.*`** values must be **repo-relative** (no leading `/`, no `http(s):`, no `../` at the start).
- **Absolute `repo_root`** for MAT-1 / MAT-2 requests stays **out of this file**; use optional `orchestration.repo_root_env` to name an environment variable your orchestrator resolves locally.

## Validate locally

```bash
cd /path/to/multi-agent-toolkit
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
python scripts/validate_ai_team_repo_profile.py
```

## YAML

Authoring in YAML is supported by tooling that loads YAML into JSON and validates the result against `repo-profile.schema.json`. The logical document is the JSON shape — this repo’s CI validates **JSON** fixtures only.
