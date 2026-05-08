# Claude Code Adapter

This adapter makes MAT skills available in Claude Code as slash commands.

## Installation

The multi-agent-toolkit is designed to be installed as a local Claude Code plugin. Run the setup script once from the repository root so Python dependencies, schema validators, tests, plugin registration, agent copies, and **Cursor personal skills** are applied automatically. (Cursor-specific behavior is documented in `../cursor/README.md`.)

### Automated setup

**Windows (PowerShell)**

```powershell
.\bin\setup.ps1
```

Optional dry run (Python + CLI checks only, no venv install, validators, tests, plugin registration, or Cursor skill install):

```powershell
.\bin\setup.ps1 --check
```

**macOS / Linux**

```bash
bin/setup
```

Optional checks only:

```bash
bin/setup --check
```

The setup scripts:

- Ensure Python 3.10+ and a `.venv` with hash-pinned dev dependencies (`requirements-dev.txt`).
- Run every `scripts/validate_*.py` validator and the `mat_runtime` unit tests (skipped automatically if `pip install` failed mid-setup).
- Register this repository in Claude Code's user plugin list by merging `multi-agent-toolkit@local` into `installed_plugins.json` (`%USERPROFILE%\.claude\plugins\` on Windows, `~/.claude/plugins/` on macOS/Linux). The merge step uses the same interpreter as the validators—the `.venv` `python` after `bin/setup` / `setup.ps1`—not whatever bare `python` happens to be on your PATH if you run pieces manually.
- Copy agent markdown from `agents/*.md` and `agents/variants/*.md` into your user `~/.claude/agents/` directory (excluding `README.md`, flattened into one folder).
- Install Cursor Agent Skills under `~/.cursor/skills/multi-agent-toolkit-*` with absolute paths to this checkout (see `../cursor/README.md`).

After setup, restart Claude Code so the plugin and copied agents reload. Restart Cursor if you use the MAT skills there too.

### Plugin layout

```
multi-agent-toolkit/
├── .claude-plugin/
│   └── plugin.json       # Plugin metadata (skill paths, name, version)
└── .claude/skills/       # Claude Code SKILL.md stubs → lib/skills
    ├── develop/
    ├── diagnose/
    └── ...
```

## Available Skills

When this repo is loaded as an **installed plugin**, Claude Code namespaces slash commands by plugin id. Invoke them as **`/multi-agent-toolkit:<skill>`** (example: `/multi-agent-toolkit:develop`).

Short forms like `/develop` apply only to skills living in **that project's** `.claude/skills/` tree—not to marketplace/plugin-loaded skills.

| Command | Description |
|---------|-------------|
| `/multi-agent-toolkit:develop <task>` | Orchestrated development workflow |
| `/multi-agent-toolkit:diagnose <issue>` | Debug and investigate issues |
| `/multi-agent-toolkit:plan <goal>` | Plan and decompose tasks |
| `/multi-agent-toolkit:review-pr <target>` | Code review for pull requests |
| `/multi-agent-toolkit:test <task>` | Write and run tests |
| `/multi-agent-toolkit:ticket <action>` | Create, list, update tickets |

## Verification

After restarting Claude Code, check for the skills:

```bash
# Examples:
# multi-agent-toolkit:develop
# multi-agent-toolkit:diagnose
```

Or type `/multi-agent-toolkit:` and let autocomplete list skills under this plugin.

## Troubleshooting

### Skills not appearing after restart

1. Verify the plugin is registered (path is your actual clone, not a placeholder):

   ```bash
   cat ~/.claude/plugins/installed_plugins.json | grep multi-agent-toolkit
   ```

   On Windows PowerShell:

   ```powershell
   Select-String -Path "$env:USERPROFILE\.claude\plugins\installed_plugins.json" -Pattern "multi-agent-toolkit"
   ```

2. Verify the plugin metadata and skill folders exist under your clone:

   ```bash
   ls path/to/multi-agent-toolkit/.claude-plugin/plugin.json
   ls path/to/multi-agent-toolkit/.claude/skills/
   ```

### Skill invocation fails

1. Ensure Python 3.10+ is installed
2. Run `.\bin\setup.ps1` (Windows) or `bin/setup` (macOS/Linux) from the toolkit root to install dependencies
3. Activate `.venv` and check that `mat_runtime` is importable: `python -c "import mat_runtime"`

### Skills do not appear when Claude Code opens **another** repository

Claude Code only loads plugins from **your user plugin registry**, not from the repo you opened—but slash commands are **namespaced**:

1. **Use the plugin prefix:** invoke `/multi-agent-toolkit:develop` (or type `/multi-agent-toolkit:` and use autocomplete), not bare `/develop`. Bare `/develop` is for skills defined inside **that project’s** `.claude/skills/`, not for installed plugins.
2. **Confirm registration:** `installed_plugins.json` must list `multi-agent-toolkit@local` with `installPath` pointing at your **actual toolkit clone** (rerun `bin/setup` / `setup.ps1` from that clone after moving it).
3. **Reload:** restart Claude Code or run `/reload-plugins` after changing registration or plugin files.
4. **Managed installs:** if your team uses managed Claude Code settings, ensure this marketplace/local plugin is **allowed/enabled** in Settings → Plugins (wording varies by version).

## See Also

- `../../.claude/skills/` — Canonical Claude Code skill stubs
- `../../mat_runtime/` — Runtime adapter layer
- `../../docs/adr/0003-skill-naming-and-fluency-alignment.md` — Naming conventions
