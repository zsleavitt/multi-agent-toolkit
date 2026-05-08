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
- Register the **mat-toolkit** marketplace and install **multi-agent-toolkit@mat-toolkit** via the Claude CLI (`scripts/register_mat_claude_plugin.py`, called from setup). Plugins are always **name@marketplace** ([Discover and install plugins](https://code.claude.com/docs/en/discover-plugins)); there is no special `@local` install channel—`local` is just another marketplace id, so older `multi-agent-toolkit@local` registry keys do not load the plugin.
- Copy agent markdown from `agents/*.md` and `agents/variants/*.md` into your user `~/.claude/agents/` directory (excluding `README.md`, flattened into one folder).
- Install Cursor Agent Skills under `~/.cursor/skills/multi-agent-toolkit-*` with absolute paths to this checkout (see `../cursor/README.md`).

After setup, restart Claude Code **or run `/reload-plugins`** so the plugin, agents, and `enabledPlugins` take effect. Restart Cursor if you use the MAT skills there too.

### Plugin layout

```
multi-agent-toolkit/
├── .claude-plugin/
│   ├── marketplace.json  # Catalog id: mat-toolkit (required for Claude Code)
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

### Manual Claude registration (if you skipped setup)

Requires `claude` on your PATH:

```bash
claude plugin marketplace add /absolute/path/to/multi-agent-toolkit --scope user
claude plugin install multi-agent-toolkit@mat-toolkit --scope user
/reload-plugins
```

### Debug log says “not found in marketplace local”

That message means Claude is trying to resolve **multi-agent-toolkit@local**. There is no built-in **local** marketplace unless you define one. This repo ships **.claude-plugin/marketplace.json** with id **mat-toolkit**; the install id must be **multi-agent-toolkit@mat-toolkit**.

1. Run `claude plugin marketplace list` and confirm **mat-toolkit** is present (add it with `claude plugin marketplace add <path-to-this-repo>` if not).
2. Run `claude plugin install multi-agent-toolkit@mat-toolkit --scope user`.
3. In `~/.claude/settings.json`, ensure `"multi-agent-toolkit@mat-toolkit": true` under `enabledPlugins`. Optional: `python scripts/enable_claude_plugin_in_user_settings.py`.
4. Remove stale toggles if you added them by mistake: uninstall **`multi-agent-toolkit@local`** via `/plugin` → Installed, or `claude plugin uninstall multi-agent-toolkit@local`.
5. Run **`claude --debug`** and check the log for plugin or MCP errors. A failing **GitHub** plugin MCP (missing `GITHUB_PERSONAL_ACCESS_TOKEN`) is separate from MAT skills but still counts as a load error in `/reload-plugins`.

Installed copies live under **`~/.claude/plugins/cache/mat-toolkit/multi-agent-toolkit/<version>/`** after install; that is expected.

**No symlink is required** for a normal clone. See [Plugins reference — debugging](https://code.claude.com/docs/en/plugins-reference#debugging-and-development-tools).

### Skills not appearing after restart

1. Verify installation and enablement:

   ```bash
   grep multi-agent-toolkit ~/.claude/plugins/installed_plugins.json
   grep mat-toolkit ~/.claude/settings.json
   ```

   On Windows PowerShell:

   ```powershell
   Select-String -Path "$env:USERPROFILE\.claude\plugins\installed_plugins.json" -Pattern "multi-agent-toolkit"
   Select-String -Path "$env:USERPROFILE\.claude\settings.json" -Pattern "mat-toolkit"
   ```

2. Verify manifests and skills exist in this repo:

   ```bash
   ls path/to/multi-agent-toolkit/.claude-plugin/marketplace.json
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
2. **Confirm `enabledPlugins`:** `"multi-agent-toolkit@mat-toolkit": true`. See *Debug log says “not found in marketplace local”* above.
3. **Reload:** restart Claude Code or run `/reload-plugins` after changing registration or plugin files.
4. **Managed installs:** if your team uses managed Claude Code settings, ensure this marketplace/local plugin is **allowed/enabled** in Settings → Plugins (wording varies by version).

## See Also

- `../../.claude/skills/` — Canonical Claude Code skill stubs
- `../../mat_runtime/` — Runtime adapter layer
- `../../docs/adr/0003-skill-naming-and-fluency-alignment.md` — Naming conventions
