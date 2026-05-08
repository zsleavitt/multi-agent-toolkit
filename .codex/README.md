# Codex Configuration

This directory contains [Codex](https://openai.com/codex) configuration for the multi-agent-toolkit.

## Prerequisites

Enable hooks in your user config (`~/.codex/config.toml`):

```toml
[features]
codex_hooks = true
```

See `config.toml.example` in this directory for a copy-paste snippet.

## Trust Model

Codex loads project-local `.codex/` configuration only when the directory is **trusted**. On first use, Codex prompts you to trust this repository. This is a security measure — hooks run arbitrary code.

If you cloned this repo and see "untrusted project" warnings:
1. Review the hooks in `hooks.json` and `hooks/` scripts
2. Trust the project when prompted by Codex

## Hooks Overview

| Hook | File | Purpose |
|------|------|---------|
| SessionStart | `hooks/mat_context.py` | Injects MAT context (contracts, role boundaries) |

## Directory Layout

```
.codex/
├── README.md              # This file
├── hooks.json             # Hook event → command mappings
├── config.toml.example    # User config snippet for enabling hooks
└── hooks/
    └── mat_context.py     # SessionStart handler
```

## Relationship to Other Adapters

- **Claude Code**: `.claude/skills/`, `.claude-plugin/plugin.json`
- **Cursor**: `.cursor/skills/`, `adapters/cursor/.cursorrules`
- **Codex**: This directory (`.codex/`)

All adapters point to shared content in `lib/skills/` and follow MAT-16 provider routing.

## References

- [Codex Hooks Documentation](https://developers.openai.com/codex/hooks)
- [Codex AGENTS.md Guide](https://developers.openai.com/codex/guides/agents-md)
- `adapters/codex/README.md` (adapter documentation)
- `CLAUDE.md` (orchestrator contract — Codex is a MAT-2 worker, not orchestrator)
