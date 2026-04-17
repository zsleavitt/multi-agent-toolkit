# Shared Skill Library

This directory contains the **shared skill content** that is referenced by platform-specific skill stubs.

## Architecture

```
lib/skills/                     # Shared content (source of truth)
├── README.md                   # This file
├── __init__.py
├── formatting.py               # Shared formatting utilities
├── develop/
│   ├── instructions.md         # Full documentation
│   └── develop.py              # Python implementation
├── diagnose/
│   ├── instructions.md
│   └── diagnose.py
├── plan/
│   ├── instructions.md
│   └── plan.py
├── review-pr/
│   ├── instructions.md
│   └── review_pr.py
├── test/
│   ├── instructions.md
│   └── test.py
└── ticket/
    ├── instructions.md
    └── ticket.py

.claude/skills/                 # Claude Code native location
├── develop/SKILL.md            # Stub with frontmatter + reference
├── diagnose/SKILL.md
├── plan/SKILL.md
├── review-pr/SKILL.md
├── test/SKILL.md
└── ticket/SKILL.md

.cursor/skills/                 # Cursor native location
├── develop/SKILL.md            # Stub with reference
├── diagnose/SKILL.md
├── plan/SKILL.md
├── review-pr/SKILL.md
├── test/SKILL.md
└── ticket/SKILL.md
```

## How It Works

1. **Shared content lives here** (`lib/skills/`) — This is the source of truth for skill documentation and Python implementations.

2. **Platform stubs reference shared content** — Each platform has its own skill directory (`.claude/skills/`, `.cursor/skills/`) with SKILL.md files that:
   - Contain platform-specific frontmatter (Claude) or format (Cursor)
   - Reference the shared instructions via relative paths
   - Provide quick-start examples and execution instructions

3. **Python implementations are shared** — All platforms run the same Python scripts from `lib/skills/<name>/<name>.py`.

## Adding a New Skill

1. Create the shared content:
   ```bash
   mkdir lib/skills/<skill-name>
   # Create instructions.md with full documentation
   # Create <skill-name>.py with Python implementation
   ```

2. Create Claude Code stub:
   ```bash
   mkdir .claude/skills/<skill-name>
   # Create SKILL.md with frontmatter + reference to lib
   ```

3. Create Cursor stub:
   ```bash
   mkdir .cursor/skills/<skill-name>
   # Create SKILL.md with reference to lib
   ```

## File Structure

### instructions.md

The shared documentation for a skill. Contains:
- Full usage documentation
- All examples
- Detailed execution steps
- See also references

### SKILL.md (Claude Code)

Platform-specific stub with:
- YAML frontmatter (`name`, `description`, `version`, `allowed-tools`, etc.)
- Brief description
- Link to shared instructions
- Quick-start examples
- Execution command

### SKILL.md (Cursor)

Platform-specific stub with:
- Markdown title and description
- Quick-start examples
- Step-by-step instructions
- Reference to shared instructions

## Why This Architecture?

- **Single source of truth** — Documentation and logic are maintained in one place
- **Platform-native discovery** — Each platform finds skills in its expected location
- **Minimal duplication** — Stubs are thin wrappers, not copies
- **Easy updates** — Change shared content, all platforms get the update
