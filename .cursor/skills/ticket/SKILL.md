---
name: ticket
description: Create, list, and update tickets via configured work item adapter (Notion, Linear, Jira, GitHub Issues). Use when managing project tickets from the command line.
compatibility:
  - ai-team.repo.json configuration file in repo root
  - Configured MCP server for your ticket provider (Notion, Linear, Jira, or GitHub)
---

# Ticket

Create, list, and update tickets via configured work item adapter (Notion, Linear, Jira, GitHub Issues).

## Usage

Invoke with `/ticket` followed by a subcommand and arguments:

```
/ticket create <title> [--priority P0|P1|P2] [--status STATUS]
/ticket list [--status <status>] [--limit <n>]
/ticket update <ticket-id> [--status <status>] [--priority <priority>]
```

## Examples

```
/ticket create "Add OAuth2 authentication" --priority P1
/ticket list --status Backlog
/ticket update 42 --status "In progress"
```

## Instructions

1. Parse the subcommand (create/list/update) and arguments from the text after `/ticket`
2. Run the skill script:
   ```bash
   python lib/skills/ticket/ticket.py <subcommand> <args> --repo-root "$(pwd)"
   ```
3. The script returns JSON with MCP payloads
4. Execute the appropriate MCP tool with the payload

## Requirements

- `ai-team.repo.json` configuration in the repo root with `work_item_source` configured
- A working MCP connection for your ticket provider

For complete documentation, see `lib/skills/ticket/instructions.md`.
