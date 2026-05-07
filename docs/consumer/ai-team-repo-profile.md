# Creating an `ai-team.repo.json` profile

The **MAT-9** profile (`ai-team.repo.json` or YAML parsed to the same shape) tells orchestration tooling **who the repo is**, **where artifacts live**, and **which work-item system** backs `/ticket` and related flows — without hardcoding company URLs in skills.

## Minimal mental model

| Section | Purpose |
|---------|---------|
| `schema_version` | Must match the schema your validators expect (currently `1.0.0`). |
| `identity` | Stable `id` and human `title` for the product/repo. |
| `repo` | `default_branch`, optional `path_overrides` for artifact/state dirs (repo-relative paths only). |
| `work_item_source` | Single adapter: `none`, `github_issues`, `linear`, `jira`, `notion`, `file`, … |
| `orchestration` | Optional `branch_template`, `repo_root_env`, etc. |

Full rules (paths, adapters, validation env vars) are in [`schemas/ai-team-repo-profile/v1/README.md`](../../schemas/ai-team-repo-profile/v1/README.md).

## GitHub Issues

```json
{
  "schema_version": "1.0.0",
  "identity": {
    "id": "my-service",
    "title": "My Service"
  },
  "repo": {
    "default_branch": "main",
    "path_overrides": {
      "artifacts_dir": ".mat/artifacts",
      "agent_state_dir": ".mat/state"
    }
  },
  "work_item_source": {
    "adapter": "github_issues",
    "github_issues": {
      "owner": "your-org",
      "repo": "your-repo"
    }
  },
  "orchestration": {
    "branch_template": "feat/{{id}}"
  }
}
```

`owner` and `repo` are **not** a full GitHub URL. Optional `priority_labels` and other fields are documented in [`lib/skills/ticket/instructions.md`](../../lib/skills/ticket/instructions.md).

## No external tracker

Use when you do not want `/ticket` to call an API:

```json
{
  "schema_version": "1.0.0",
  "identity": { "id": "local-only", "title": "Local only" },
  "repo": { "default_branch": "main" },
  "work_item_source": { "adapter": "none" }
}
```

See [`schemas/ai-team-repo-profile/v1/examples/valid/minimal_none.json`](../../schemas/ai-team-repo-profile/v1/examples/valid/minimal_none.json).

## Other adapters

Copy a starting point from [`schemas/ai-team-repo-profile/v1/examples/valid/`](../../schemas/ai-team-repo-profile/v1/examples/valid/):

- `linear.json`, `linear_enterprise.json`
- `jira.json`
- `notion.json`, `notion_minimal.json`
- `file_backlog.json`

Each adapter has required blocks documented in the schema README.

## Validate your file

The script `scripts/validate_ai_team_repo_profile.py` checks the **MAT-9 bundle** (schema plus built-in `examples/valid` and `examples/invalid` fixtures). It does not take a path to your repo’s file.

**Practical options for your `ai-team.repo.json`:**

1. **Editor JSON Schema** — Map `ai-team.repo.json` to `schemas/ai-team-repo-profile/v1/repo-profile.schema.json` from your MAT checkout (VS Code / Cursor: JSON Schema association in settings).
2. **One-shot check inside a MAT tree** — Copy your document to `schemas/ai-team-repo-profile/v1/examples/valid/<name>.json` in a checkout, run `python scripts/validate_ai_team_repo_profile.py`, then delete or `.gitignore` that fixture if it must not be committed.
3. **Reuse the script’s machinery** — Import `jsonschema` + `referencing` the same way as `validate_ai_team_repo_profile.py` and validate your path in a small local script.

```bash
cd /path/to/multi-agent-toolkit
source .venv/bin/activate
python scripts/validate_ai_team_repo_profile.py
```

## Relationship to `mat-config.json`

- **`ai-team.repo.json`** — MAT-9 **repo profile** (identity, portable paths, work items).
- **`mat-config.json`** or **`.mat/config.json`** — MAT-16 **CLI routing** for `mat_runtime` (which binary handles orchestrator vs worker vs git).

You typically want **both** at your consumer repo root once you run agents through `mat_runtime`.
