# Cursor Adapter

This adapter exposes MAT workflows in Cursor via **Agent Skills** (slash commands). Skills live under `.cursor/skills/` in this repository for contributors; **end users** typically install **personal** copies so the same commands work in **any** project you open in Cursor.

## Global install (any repository)

Run the toolkit setup once from your clone (same as Claude Code registration):

**Windows**

```powershell
.\bin\setup.ps1
```

**macOS / Linux**

```bash
bin/setup
```

Setup runs `scripts/install_cursor_personal_skills.py`, which writes into:

| Platform | Personal skills directory |
|----------|---------------------------|
| Windows | `%USERPROFILE%\.cursor\skills\` |
| macOS / Linux | `~/.cursor/skills/` |

Each skill is installed as its **own folder** with a `multi-agent-toolkit-*` prefix (so your personal `develop` skill, if any, is not overwritten):

- `multi-agent-toolkit-develop`
- `multi-agent-toolkit-diagnose`
- `multi-agent-toolkit-plan`
- `multi-agent-toolkit-review-pr`
- `multi-agent-toolkit-test`
- `multi-agent-toolkit-ticket`

Stubs are **rewritten** so Python invokes scripts under **your toolkit checkout** with `--repo-root` set to the **current workspace** (`pwd`). Keep one stable clone path on disk (same directory you register for Claude Code’s plugin `installPath`).

Manual reinstall (after pulling toolkit updates):

```bash
python scripts/install_cursor_personal_skills.py --repo-root /path/to/multi-agent-toolkit
```

`--dry-run` prints destinations without writing.

After installing or upgrading skills, **fully restart Cursor** (or reload the skills catalog when your Cursor version supports it) so new slash commands appear.

## Slash commands (global / personal skills)

Use the **prefixed** names Cursor discovers from folder + frontmatter:

| Command | Description |
|---------|-------------|
| `/multi-agent-toolkit-develop <task>` | Orchestrated development workflow |
| `/multi-agent-toolkit-diagnose <issue>` | Debug and investigate issues |
| `/multi-agent-toolkit-plan <goal>` | Plan and decompose tasks |
| `/multi-agent-toolkit-review-pr <target>` | Code review for PRs or paths |
| `/multi-agent-toolkit-test <task>` | Write and run tests |
| `/multi-agent-toolkit-ticket <action>` | Create / list / update tickets |

## Project-only install (legacy)

You can still copy rules into a single repo (does **not** carry to other checkouts):

```bash
cp adapters/cursor/.cursorrules /path/to/your/project/.cursorrules
```

Prefer personal skills + setup when you want MAT everywhere.

## Configuration

### Agent routing

Use MAT-16 (`agents.json` / provider config) in the **workspace** you are working on so routing matches your tooling. See `schemas/provider-config/v1/README.md`.

### Work items (`/multi-agent-toolkit-ticket`)

Requires `ai-team.repo.json` in the repo root and the MCP/server wiring documented for your adapter.

### Prerequisites

- Python on PATH when Cursor runs terminal/bash steps (skill stubs call `python "…/lib/skills/…/….py"` with an absolute path).
- Toolkit `requirements-dev.txt` installed into `.venv` if those scripts import deps (`bin/setup` does this).

## Verification

1. Restart Cursor after setup.
2. Open **any** repository as the workspace root.
3. Try `/multi-agent-toolkit-plan` with a short goal; confirm it runs `plan.py` against that repo’s `--repo-root`.

## Troubleshooting

### Slash command not found

- Confirm folders exist under `~/.cursor/skills/multi-agent-toolkit-*`.
- Restart Cursor.
- Do not place custom skills under `~/.cursor/skills-cursor/` (reserved for Cursor-built-ins).

### Script fails with “no such file”

- Re-run setup after moving the toolkit clone (paths inside installed `SKILL.md` are absolute).
- Pass `--repo-root` pointing at the live checkout when running `install_cursor_personal_skills.py` manually.

## Differences from Claude Code

| Feature | Claude Code | Cursor |
|---------|-------------|--------|
| Distribution | Plugin manifest + `installed_plugins.json` | Personal `~/.cursor/skills/` folders |
| Slash naming | `/multi-agent-toolkit:skill` | `/multi-agent-toolkit-skill` |
| Legacy project hook | — | `.cursorrules` in repo root |

## See Also

- `../../.cursor/skills/` — Source stubs (repo-relative paths before install)
- `../../mat_runtime/` — Runtime adapter layer
- `../claude-code/README.md` — Claude plugin install (same setup scripts)
