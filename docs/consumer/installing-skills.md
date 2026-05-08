# Installing MAT skills (Claude Code and Cursor)

Skills live in **`lib/skills/<name>/`** (Python + `instructions.md`). Platform stubs under **`.claude/skills/`** and **`.cursor/skills/`** tell each product how to invoke them.

## Prerequisites

- **Python 3.10+** on `PATH`
- Dependencies: `pip install -r /path/to/multi-agent-toolkit/requirements-dev.txt` (from a venv you use for MAT)
- For **`mat_runtime`**, optional CLIs: `claude`, `codex`, `gemini` (see root [README](../../README.md))

## Claude Code

Follow **[`adapters/claude-code/README.md`](../../adapters/claude-code/README.md)**:

1. Point Claude Code’s plugin install path at your **multi-agent-toolkit** checkout (submodule or global clone).
2. Register the plugin in `~/.claude/plugins/installed_plugins.json` as documented there.
3. Restart Claude Code; use `/develop`, `/plan`, `/review-pr`, `/test`, `/diagnose`, `/ticket`, `/finish-branch` (see `.claude/skills/`), and other stubs shipped with your plugin path.

The toolkit’s native stubs live under **[`.claude/skills/`](../../.claude/skills/)** in this repository.

**Orchestrator context:** merge or follow **[`CLAUDE.md`](../../CLAUDE.md)** patterns in your app repo’s root `CLAUDE.md` so the model understands MAT-1/MAT-2 boundaries and delegation.

## Cursor

1. Copy **[`adapters/cursor/.cursorrules`](../../adapters/cursor/.cursorrules)** to your project root as `.cursorrules` (or append its contents). See **[`adapters/cursor/README.md`](../../adapters/cursor/README.md)** for symlink / merge options.

2. **Fix the Python paths.** The stock rules assume `lib/skills/...` exists at **your** repo root. In a consumer repo, MAT is usually a **submodule** or **sibling directory**. Edit each `python lib/skills/...` line to an absolute or repo-relative path, for example:

   ```bash
   python vendor/multi-agent-toolkit/lib/skills/develop/develop.py "<task>" --repo-root "$(pwd)"
   ```

3. **`--repo-root`** should be your **application** repository (where `ai-team.repo.json` and code live), not necessarily the MAT checkout.

### MAT-16 config for Cursor-driven runs

`mat_runtime` loads **`mat-config.json`** or **`.mat/config.json`** (not `agents.json`). See **[`schemas/provider-config/v1/README.md`](../../schemas/provider-config/v1/README.md)** and [Getting started — Wire MAT into your repo](getting-started.md).

### `/ticket` and MCP

`/ticket` may require a configured **work item MCP** (Notion, Linear, Jira, GitHub) in the orchestrator environment. Cursor rules alone do not add MCP servers; configure them in Cursor settings if you rely on ticket automation from the IDE.

## Verification

```bash
export PYTHONPATH="/path/to/multi-agent-toolkit:$PYTHONPATH"
python -c "import mat_runtime; print('mat_runtime OK')"
python /path/to/multi-agent-toolkit/lib/skills/develop/develop.py "noop check" --repo-root "$(pwd)"
```

In the editor, run `/develop` with a trivial task after wiring paths.

## See also

- [`lib/skills/README.md`](../../lib/skills/README.md) — stub layout and adding skills
- [ADR 0003 — Skill naming](../../docs/adr/0003-skill-naming-and-fluency-alignment.md)
