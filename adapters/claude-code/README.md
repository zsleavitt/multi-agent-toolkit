# Claude Code Adapter

This adapter makes MAT skills available in Claude Code as slash commands.

## Installation

The multi-agent-toolkit is designed to be installed as a local Claude Code plugin. Run the setup script once from the repository root so Python dependencies, schema validators, tests, plugin registration, and agent copies are applied automatically.

### Automated setup

**Windows (PowerShell)**

```powershell
.\bin\setup.ps1
```

Optional dry run (Python + CLI checks only, no venv install, validators, tests, or plugin registration):

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
- Run every `scripts/validate_*.py` validator and the `mat_runtime` unit tests.
- Register this repository in Claude Code’s user plugin list by merging `multi-agent-toolkit@local` into `installed_plugins.json` (`%USERPROFILE%\.claude\plugins\` on Windows, `~/.claude/plugins/` on macOS/Linux).
- Copy top-level agent markdown files from `agents/*.md` into your user `.claude/agents/` directory (excluding `README.md`).

After setup, restart Claude Code so the plugin and copied agents reload.

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

After installation, these slash commands become available (namespaced by the plugin id, e.g. `multi-agent-toolkit:develop`):

| Command | Description |
|---------|-------------|
| `/develop <task>` | Orchestrated development workflow |
| `/diagnose <issue>` | Debug and investigate issues |
| `/plan <goal>` | Plan and decompose tasks |
| `/review-pr <target>` | Code review for pull requests |
| `/test <task>` | Write and run tests |
| `/ticket <action>` | Create, list, update tickets |

## Verification

After restarting Claude Code, check for the skills:

```bash
# The skills should appear as:
# multi-agent-toolkit:develop
# multi-agent-toolkit:diagnose
# etc.
```

Or type `/develop` and see if it autocompletes.

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
3. Check that `mat_runtime` is importable: `python -c "import mat_runtime"`

## See Also

- `../../.claude/skills/` — Canonical Claude Code skill stubs
- `../../mat_runtime/` — Runtime adapter layer
- `../../docs/adr/0003-skill-naming-and-fluency-alignment.md` — Naming conventions
