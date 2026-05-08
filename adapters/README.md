# Tool Adapters

This directory contains additional tool-specific configuration for discovering and invoking MAT skills. The main skill discovery now uses **platform-native locations** (`.claude/skills/`, `.cursor/skills/`), while adapters provide supplementary configuration.

## Architecture

```
lib/skills/                ← Shared content (source of truth)
├── develop/
│   ├── instructions.md    ← Full documentation
│   └── develop.py         ← Python implementation
└── .../

.claude/skills/            ← Claude Code native location
├── develop/SKILL.md       ← Stub with frontmatter + reference
└── .../

.cursor/skills/            ← Cursor native location
├── develop/SKILL.md       ← Stub with reference
└── .../

adapters/                  ← Supplementary tool configuration
├── claude-code/
│   └── README.md          ← Claude Code setup instructions
├── cursor/
│   ├── README.md          ← Cursor skills setup (global + optional .cursorrules)
│   └── .cursorrules       ← Optional legacy project rules snippet
└── README.md              ← This file
```

## How It Works

1. **Shared content lives in `lib/skills/`** — Documentation and Python implementations are maintained here.

2. **Platform stubs in native locations** — `.claude/skills/` and `.cursor/skills/` contain SKILL.md files that reference the shared content.

3. **Adapters provide extras** — Claude Code plugin metadata under `.claude-plugin/`; Cursor defaults to personal skills installed via `bin/setup` (see `adapters/cursor/README.md`) with optional `.cursorrules`.

4. **Execution is unified** — All tools run `python lib/skills/*/skill.py`, which uses `mat_runtime` to route to the configured CLI tool.

## Supported Tools

| Tool | Adapter | Installation |
|------|---------|--------------|
| Claude Code | `.claude-plugin/plugin.json` (repo root) | See `claude-code/README.md` |
| Cursor | `scripts/install_cursor_personal_skills.py` + personal `~/.cursor/skills/` (wired by `bin/setup`; optional `.cursorrules`) | See `cursor/README.md` |
| Codex | `.codex/hooks.json` + `~/.codex/config.toml` feature flag | See `codex/README.md` |
| Direct CLI | None needed | Run `python lib/skills/*/*.py` directly |

## Adding New Tool Adapters

To add support for a new tool:

1. Create a directory: `adapters/<tool-name>/`
2. Add the tool's discovery configuration file
3. Add a README.md with installation instructions
4. The adapter should point to the canonical `skills/` location

## MAT-16 Provider Configuration

The runtime behavior (which CLI tool handles which role) is controlled by `agents.json` (MAT-16 schema), not the adapters. Adapters handle **discovery**; MAT-16 handles **execution routing**.

Example `agents.json`:
```json
{
  "schema_version": "1.0.0",
  "agents": {
    "orchestrator": { "cli": "claude", "capabilities": ["planning", "routing"] },
    "worker": { "cli": "codex", "capabilities": ["implement", "test"] }
  }
}
```

See `schemas/provider-config/v1/README.md` for full documentation.
