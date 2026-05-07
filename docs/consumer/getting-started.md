# Getting started in a consumer repository

MAT is **repo-agnostic**: you bring JSON Schemas, validators, `mat_runtime`, skills, and optional `agents/` definitions. Nothing requires a fixed org URL.

## Choose how you depend on MAT

### A. Git submodule (pinned revision)

Good when you want a **stable SHA** and explicit upgrades.

```bash
cd /path/to/your/repo
git submodule add https://github.com/zsleavitt/multi-agent-toolkit.git vendor/multi-agent-toolkit
git submodule update --init --recursive
```

Point scripts and `PYTHONPATH` at `vendor/multi-agent-toolkit`.

### B. Clone beside your repo (local path)

Good for **trying MAT** before you commit a submodule or copy.

```bash
git clone https://github.com/zsleavitt/multi-agent-toolkit.git ~/mat/multi-agent-toolkit
export PYTHONPATH="$HOME/mat/multi-agent-toolkit:$PYTHONPATH"
```

Use absolute paths in editor/plugin config so they survive cwd changes.

### C. Editable install (Python env)

Good when you **patch MAT** from your monorepo or need imports without `PYTHONPATH`.

```bash
pip install -e /path/to/multi-agent-toolkit
```

Use the same virtualenv your team already uses for tooling, or a dedicated `.venv` per repo.

## One-time setup inside MAT’s tree

If you are working **from a checkout** of multi-agent-toolkit (submodule or clone), run:

```bash
cd /path/to/multi-agent-toolkit
bin/setup
```

That creates `.venv`, installs `requirements-dev.txt`, checks optional CLIs (`claude`, `codex`, `gemini`), and runs validators plus `mat_runtime` tests.

**Check-only** (CI or laptops without full toolchain):

```bash
bin/setup --check
```

## Wire MAT into *your* repo root

1. **Profile** — Add [`ai-team.repo.json`](ai-team-repo-profile.md) at your repository root (identity, paths, optional `work_item_source`).
2. **MAT-16 runtime config** — Add `mat-config.json` or `.mat/config.json` so `mat_runtime` knows which CLIs map to orchestrator / worker / git-executor. See [`schemas/provider-config/v1/README.md`](../../schemas/provider-config/v1/README.md).
3. **Agents** — Either copy [`agents/`](../../agents/) from MAT and customize Markdown definitions, or maintain your own `agents/*.md` that satisfy [`schemas/agent-definition/v1/`](../../schemas/agent-definition/v1/).
4. **Skills** — Install [Claude Code plugin / Cursor rules](installing-skills.md) so slash commands resolve to `lib/skills/*` in your MAT checkout.

## Prove the install

From your consumer repo (with `PYTHONPATH` or editable install pointing at MAT):

```bash
python -m mat_runtime list-agents
python -m mat_runtime smoke
```

Optional strict preflight for images that must have every CLI:

```bash
python -m mat_runtime smoke --strict
```

Validate the MAT-9 schema bundle (built-in examples) from your checkout:

```bash
python /path/to/multi-agent-toolkit/scripts/validate_ai_team_repo_profile.py
```

For validating **your** profile document specifically, see [ai-team-repo-profile.md — Validate your file](ai-team-repo-profile.md#validate-your-file). Use `MAT_AI_TEAM_REPO_PROFILE_V1` if the bundle is not at the default relative path (see the schema README).

## Orchestrator context

If you use **Claude Code** as the orchestrator, add or merge toolkit guidance into your root **`CLAUDE.md`** (or equivalent). The toolkit ships [`CLAUDE.md`](../../CLAUDE.md) as a reference for how planning, MAT-1/MAT-2 routing, and security constraints are described to the model.

## Next steps

- Configure **[`ai-team.repo.json`](ai-team-repo-profile.md)** for tickets and portable paths.
- **[Install skills](installing-skills.md)** in your editor.
- Follow **[example workflows](workflows.md)** for day-to-day use.
