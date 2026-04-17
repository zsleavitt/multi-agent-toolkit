# Claude Code Adapter

This adapter makes MAT skills available in Claude Code as slash commands.

## Installation

The multi-agent-toolkit is designed to be installed as a local Claude Code plugin.

### Step 1: Create the plugin metadata

The plugin needs a `.claude-plugin/plugin.json` file at the repository root (already created):

```
multi-agent-toolkit/
├── .claude-plugin/
│   └── plugin.json    # Plugin metadata
└── skills/            # Skill definitions
    ├── develop/
    │   └── SKILL.md
    ...
```

### Step 2: Register in installed_plugins.json

Add the following entry to `~/.claude/plugins/installed_plugins.json`:

```json
"multi-agent-toolkit@local": [
  {
    "scope": "user",
    "installPath": "/Users/<your-username>/.claude/multi-agent-toolkit",
    "version": "1.0.0",
    "installedAt": "2026-04-17T10:00:00.000Z",
    "lastUpdated": "2026-04-17T10:00:00.000Z"
  }
]
```

### Step 3: Restart Claude Code

Exit and restart Claude Code to pick up the new plugin. After restart, the skills should appear in autocomplete when typing `/`.

## Available Skills

After installation, these slash commands become available:

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

1. Verify the plugin is registered:
   ```bash
   cat ~/.claude/plugins/installed_plugins.json | grep multi-agent-toolkit
   ```

2. Verify the plugin structure:
   ```bash
   ls ~/.claude/multi-agent-toolkit/.claude-plugin/plugin.json
   ls ~/.claude/multi-agent-toolkit/skills/
   ```

3. Check that each skill has a `SKILL.md` file with valid frontmatter

### Skill invocation fails

1. Ensure Python 3.10+ is installed
2. Run `bin/setup` from the toolkit root to install dependencies
3. Check that `mat_runtime` is importable: `python -c "import mat_runtime"`

## See Also

- `../../skills/` — Canonical skill definitions
- `../../mat_runtime/` — Runtime adapter layer
- `../../docs/adr/0003-skill-naming-and-fluency-alignment.md` — Naming conventions
