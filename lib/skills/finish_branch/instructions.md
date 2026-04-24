# finish-branch

Closes or transitions work items when a development branch is merged. Reads the configured work item source from `ai-team.repo.json` and dispatches to the appropriate adapter.

## Usage

```
/finish-branch [--branch BRANCH] [--comment COMMENT] [--dry-run]
```

## Examples

### Close work item for current branch
```
/finish-branch
```

### Close with a comment
```
/finish-branch --comment "Merged in PR #100"
```

### Specify branch explicitly
```
/finish-branch --branch feat/mat-42-crew-schema
```

### Dry run to see what would happen
```
/finish-branch --dry-run
```

## How It Works

1. **Extract work item reference** from branch name
   - `feat/mat-42-crew-schema` -> `MAT-42`
   - `fix/PROJ-123-bug` -> `PROJ-123`

2. **Read adapter config** from `ai-team.repo.json`
   - Supports: `github_issues`, `jira`, `notion`, `file`, `none`

3. **Close/transition** via appropriate adapter
   - GitHub: `gh issue close` after lookup
   - Jira: REST API transition to Done
   - Notion: Update status property
   - file/none: No-op with informational message

## Configuration

The skill reads `work_item_source` from `ai-team.repo.json`:

### GitHub Issues
```json
{
  "work_item_source": {
    "adapter": "github_issues",
    "github_issues": {
      "owner": "your-org",
      "repo": "your-repo"
    }
  }
}
```

### Jira
```json
{
  "work_item_source": {
    "adapter": "jira",
    "jira": {
      "base_url": "https://company.atlassian.net",
      "project_key": "PROJ",
      "done_transition": "Done"
    }
  }
}
```

Requires environment variables: `JIRA_EMAIL`, `JIRA_API_TOKEN`

### Notion
```json
{
  "work_item_source": {
    "adapter": "notion",
    "notion": {
      "database_id": "your-database-uuid",
      "status_property": "Status",
      "done_value": "Done"
    }
  }
}
```

Requires environment variable: `NOTION_API_KEY`

## Supported Adapters

| Adapter | Implementation | Notes |
|---------|---------------|-------|
| `github_issues` | Full | Uses `gh` CLI |
| `jira` | Stub | Needs REST API implementation |
| `notion` | Stub | Needs API implementation |
| `file` | No-op | Informational message only |
| `none` | No-op | Informational message only |

## Execution

```bash
python lib/skills/finish_branch/finish_branch.py --branch <branch>
```

## See Also

- `ai-team.repo.json` - Repository configuration (MAT-9)
- `/ticket` skill - Create and manage work items
- CLAUDE.md PR Creation - Issue linking for PRs
