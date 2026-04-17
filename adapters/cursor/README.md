# Cursor Adapter

This adapter makes MAT skills available in Cursor as slash commands via `.cursorrules`.

## Installation

### Option 1: Copy to your project (recommended)

Copy the `.cursorrules` file to your project root:

```bash
cp adapters/cursor/.cursorrules /path/to/your/project/.cursorrules
```

Or append to an existing `.cursorrules`:

```bash
cat adapters/cursor/.cursorrules >> /path/to/your/project/.cursorrules
```

### Option 2: Symlink (for development)

```bash
ln -s /path/to/multi-agent-toolkit/adapters/cursor/.cursorrules /path/to/your/project/.cursorrules
```

### Option 3: Include via reference

Add to your existing `.cursorrules`:

```markdown
# Include MAT skills
@import /path/to/multi-agent-toolkit/adapters/cursor/.cursorrules
```

## Available Skills

After installation, these commands become available:

| Command | Description |
|---------|-------------|
| `/develop <task>` | Orchestrated development workflow |
| `/diagnose <issue>` | Debug and investigate issues |
| `/plan <goal>` | Plan and decompose tasks |
| `/review-pr <target>` | Code review for pull requests |
| `/test <task>` | Write and run tests |
| `/ticket <action>` | Create, list, update tickets |

## How It Works

Cursor loads `.cursorrules` files from the project root. When you type a command like `/develop`, Cursor's AI:

1. Reads the instructions from `.cursorrules`
2. Executes the corresponding Python script
3. Presents the results

## Configuration

### Agent Routing

Create `agents.json` in your project root to configure which CLI tools handle each role:

```json
{
  "schema_version": "1.0.0",
  "agents": {
    "default": {
      "cli": "cursor",
      "capabilities": ["planning", "routing", "implement", "test", "review"]
    }
  }
}
```

This tells MAT to use Cursor for all agent roles. See `schemas/provider-config/v1/README.md` for other configurations.

### Work Item Integration

For `/ticket` commands, create `ai-team.repo.json`:

```json
{
  "identity": { "name": "my-project" },
  "work_item_source": {
    "adapter": "github_issues"
  }
}
```

## Prerequisites

1. Python 3.10+ in your PATH
2. MAT dependencies installed: `pip install -r /path/to/multi-agent-toolkit/requirements-dev.txt`
3. MAT in PYTHONPATH or installed

### Quick Setup

```bash
# From your project directory
export PYTHONPATH="/path/to/multi-agent-toolkit:$PYTHONPATH"

# Or install MAT as editable
pip install -e /path/to/multi-agent-toolkit
```

## Verification

1. Open Cursor in your project
2. Type `/develop` — Cursor should recognize it as a command
3. Try `/develop Add a hello world function`

## Troubleshooting

### Commands not recognized

- Ensure `.cursorrules` is in the project root
- Restart Cursor after adding the file
- Check Cursor settings: File > Preferences > Settings > "cursorrules"

### Python script fails

1. Check Python is available: `which python`
2. Verify mat_runtime: `python -c "from mat_runtime import router"`
3. Check PYTHONPATH includes the toolkit

### Agent not found

Create `agents.json` with at least a `default` agent configuration.

## Differences from Claude Code

| Feature | Claude Code | Cursor |
|---------|-------------|--------|
| Skill discovery | Plugin system | `.cursorrules` file |
| MCP tools | Full support | Limited/none |
| Slash commands | Native | Via rules file |

Note: Some features like `/ticket` rely on MCP tools that may not be available in Cursor. These commands will work if you configure `agents.json` to route to a CLI that has the required integrations.

## See Also

- `../../skills/` — Canonical skill definitions
- `../../mat_runtime/` — Runtime adapter layer
- `../../schemas/provider-config/v1/` — Agent configuration schema
