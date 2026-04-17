---
name: ticket
description: Create, list, and update tickets via configured work item adapter (Notion, Linear, Jira, GitHub Issues).
version: 1.0.0
disable-model-invocation: true
allowed-tools: Bash(python *)
---

# Ticket

Creates, lists, and updates tickets in your configured work item system.

For complete documentation, see [instructions.md](../../../lib/skills/ticket/instructions.md).

## Quick Start

```
/ticket create <title> [--priority P0|P1|P2] [--status STATUS]
/ticket list [--status <status>] [--limit <n>]
/ticket update <ticket-id> [--status <status>] [--priority <priority>]
```

## Examples

- `/ticket create "Add OAuth2 authentication" --priority P1`
- `/ticket list --status Backlog`
- `/ticket update 42 --status "In progress"`

## Execution

Run the skill script to get MCP payloads:

```bash
python lib/skills/ticket/ticket.py $ARGUMENTS --repo-root "$(pwd)"
```

Then execute the MCP tool call with the returned payload.

## Configuration

Reads from `ai-team.repo.json` in the repo root. See the full instructions for configuration details.
