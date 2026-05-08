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
- Register this repository in Claude Code's user registry: merge `multi-agent-toolkit@local` into `installed_plugins.json`, and set matching keys under `enabledPlugins` in `~/.claude/settings.json` (via `scripts/enable_claude_plugin_in_user_settings.py`). **Installed ≠ enabled**: Claude Code usually requires both; see [Plugin settings](https://code.claude.com/docs/en/settings#plugin-settings).
- Copy agent markdown from `agents/*.md` and `agents/variants/*.md` into your user `~/.claude/agents/` directory (excluding `README.md`, flattened into one folder).
- Install Cursor Agent Skills under `~/.cursor/skills/multi-agent-toolkit-*` with absolute paths to this checkout (see `../cursor/README.md`).

After setup, restart Claude Code **or run `/reload-plugins`** so the plugin, agents, and `enabledPlugins` take effect. Restart Cursor if you use the MAT skills there too.

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

**Note:** Third-party advice to use bare `/develop`, `/plan`, etc. after a plugin install is often wrong. Namespaced plugins expose **`/multi-agent-toolkit:<skill>`** (colon between plugin id and skill name), not the same short paths as project-local `.claude/skills/`.

## Troubleshooting

### installed_plugins.json looks correct but skills still do not load

Claude Code separates **installation** (`~/.claude/plugins/installed_plugins.json`) from **enabling** (`enabledPlugins` in `~/.claude/settings.json`). Setup updates both. Verify:

```bash
grep -A2 enabledPlugins ~/.claude/settings.json | head
```

You should see `multi-agent-toolkit@local` and path-scoped keys (forward slashes and, on Windows, the native drive path) set to `true`. Then run `/reload-plugins`.

Registry **version 2** keeps installs under the top-level `"plugins"` object in `installed_plugins.json`. If `multi-agent-toolkit@local` only appears as a loose key next to `"version"` and not under `"plugins"`, Claude Code will not load the toolkit; re-run `bin/setup` / `bin/setup.ps1` from the clone so the merge script can fix it.

**No symlink is required** for a local clone: `installPath` should point at your real checkout. Use `claude --debug` if you need plugin load traces ([Plugins reference — debugging](https://code.claude.com/docs/en/plugins-reference#debugging-and-development-tools)).

**Official alternative:** install from a terminal (also updates enablement in supported versions):

```bash
claude plugin install /absolute/path/to/multi-agent-toolkit
```

(or `claude plugin install` with your platform’s path). Afterward run `/reload-plugins`.

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
2. **Confirm `enabledPlugins`:** see *installed_plugins.json looks correct but skills still do not load* above.
3. **Reload:** restart Claude Code or run `/reload-plugins` after changing registration or plugin files.
4. **Managed installs:** if your team uses managed Claude Code settings, ensure this marketplace/local plugin is **allowed/enabled** in Settings → Plugins (wording varies by version).

## See Also

- `../../.claude/skills/` — Canonical Claude Code skill stubs
- `../../mat_runtime/` — Runtime adapter layer
- `../../docs/adr/0003-skill-naming-and-fluency-alignment.md` — Naming conventions
