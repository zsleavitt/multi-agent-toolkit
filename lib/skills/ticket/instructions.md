# Ticket

Creates, lists, and updates tickets in your configured work item system (Notion, Linear, Jira, GitHub Issues). Reads configuration from `ai-team.repo.json`.

## Usage

```
/ticket create <title> [--priority P0|P1|P2] [--status Backlog|Ready|...]
/ticket list [--status <status>] [--limit <n>]
/ticket update <ticket-id> [--status <status>] [--priority <priority>]
```

## Examples

### Create a ticket
```
/ticket create "Add OAuth2 authentication" --priority P1
```

### List backlog tickets
```
/ticket list --status Backlog
```

### Update ticket status
```
/ticket update 42 --status "In progress"
```

### Create with description
```
/ticket create "Fix login bug" --priority P0 --description "Users can't login after password reset"
```

## Configuration

The skill reads from `ai-team.repo.json` in the repo root:

```json
{
  "work_item_source": {
    "adapter": "notion",
    "notion": {
      "database_id": "your-database-uuid",
      "field_map": {
        "title": "Name",
        "status": "Status",
        "priority": "Priority"
      }
    }
  }
}
```

## Supported Adapters

| Adapter | MCP Required | Status |
|---------|--------------|--------|
| `notion` | Notion MCP | Implemented |
| `linear` | Linear MCP | Planned |
| `jira` | Jira MCP | Planned |
| `github_issues` | GitHub MCP | Planned |

## Architecture

This skill runs in the **orchestrator context** (Claude Code) where MCPs are available. It does not delegate to workers.

```
/ticket skill
    |
NotionAdapter (builds payloads)
    |
Notion MCP tools (notion-create-pages, notion-query-data-sources)
```

## Execution

When the user invokes this skill:

1. Parse the command (create/list/update) and arguments

2. Load the work item adapter:
   ```python
   from mat_runtime.work_items import get_adapter_from_profile
   adapter = get_adapter_from_profile(repo_root)
   ```

3. For **create**:
   - Build a WorkItem with title, status, priority, description
   - Use `adapter.build_create_payload(item)` to get Notion payload
   - Call `notion-create-pages` MCP tool with the payload
   - Report the created ticket ID

4. For **list**:
   - Use `adapter.build_query(status, limit)` to get SQL query
   - Call `notion-query-data-sources` MCP tool
   - Use `adapter.parse_notion_results()` to format output

5. For **update**:
   - Build a WorkItem with id and fields to update
   - Use `adapter.build_update_payload(item)` to get Notion payload
   - Call `notion-update-page` MCP tool

## Error Handling

- If `ai-team.repo.json` not found: Suggest running setup wizard
- If adapter is "none": Report that no ticket system is configured
- If MCP tool fails: Report the error with suggestions

## See also

- `ai-team.repo.json` — Repository configuration
- ADR 0004 — MCP and tool capabilities architecture
- MAT-35 — Setup wizard for configuring ticket provider
