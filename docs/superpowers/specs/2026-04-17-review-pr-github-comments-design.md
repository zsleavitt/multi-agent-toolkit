# Design: /review-pr GitHub PR Comments

**Date:** 2026-04-17  
**Status:** Approved  
**Ticket:** Skill review-pr should post comments to PR

## Overview

Extend `/review-pr` to post review findings as inline comments on GitHub PRs via the `gh` CLI.

## Requirements

| Requirement | Decision |
|-------------|----------|
| Default behavior | CLI-only; `--post` flag enables GitHub posting |
| Comment style | Inline comment per finding + brief summary |
| No PR exists | Prompt user to create one |
| Severity filter | `--min-severity` flag, default `info` (post all) |
| Review status | Auto: REQUEST_CHANGES if blocker/issue, else COMMENT |

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      review_pr.py                           │
│  (existing: invokes reviewer agent, formats output)         │
└─────────────────────┬───────────────────────────────────────┘
                      │ --post flag
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                  github_review.py (NEW)                     │
│  - detect_pr_for_branch()                                   │
│  - build_review_payload(findings, min_severity)             │
│  - post_review(payload) → gh pr review                      │
│  - format_summary(findings) → brief count string            │
└─────────────────────────────────────────────────────────────┘
                      │
                      ▼
              gh api repos/{owner}/{repo}/pulls/{pr}/reviews
                         --method POST
                         --input <payload.json>
```

### New Files

- `lib/skills/review-pr/github_review.py` — GitHub interaction module

### Modified Files

- `lib/skills/review-pr/review_pr.py` — add `--post`, `--min-severity` flags

## CLI Interface

```
/review-pr <target> [--post] [--min-severity info|suggestion|issue|blocker]
```

**New flags:**
- `--post` — Post findings as GitHub PR review (default: false)
- `--min-severity` — Minimum severity to post (default: info)

## Data Flow

1. Run reviewer agent → get `MAT2Response` with `findings[]`
2. If `--post`:
   a. Call `detect_pr_for_branch()` via `gh pr view --json number,headRefName`
   b. If no PR: prompt "No PR found. Create one? [y/N]"
      - Yes: run `gh pr create` interactively, continue
      - No: fall back to CLI output only
   c. Filter findings by `--min-severity`
   d. Build review payload with event type and comments
   e. Build JSON payload with event, body, and comments array
   f. Run `gh api repos/{owner}/{repo}/pulls/{pr}/reviews --method POST --input <payload.json>`
3. Print CLI output as usual
4. If posted: print "Posted review to PR #N"

## Comment Format

### Inline Comment Body

```
**[blocker]** Security: SQL injection risk

User input concatenated directly into query string.
```

Format: `**[{severity}]** {category}: {message}`

### Summary Comment Body

```
## Review Summary

🚫 2 blockers · ⚠️ 1 issue · 💡 3 suggestions · ℹ️ 1 info

*Posted via /review-pr*
```

### GitHub API Payload

```json
{
  "event": "REQUEST_CHANGES",
  "body": "## Review Summary\n\n🚫 2 blockers · ⚠️ 1 issue\n\n*Posted via /review-pr*",
  "comments": [
    {
      "path": "src/db/query.py",
      "line": 45,
      "body": "**[blocker]** Security: SQL injection risk\n\nUser input concatenated directly into query string."
    }
  ]
}
```

### Review Event Mapping

| Condition | Event |
|-----------|-------|
| Any `blocker` or `issue` in posted findings | REQUEST_CHANGES |
| Only `suggestion` and/or `info` | COMMENT |

## Error Handling

| Scenario | Behavior |
|----------|----------|
| `gh` CLI not installed | Error: "GitHub CLI (gh) not found. Install from https://cli.github.com" |
| `gh` not authenticated | Error: "GitHub CLI not authenticated. Run `gh auth login`" |
| No PR + user declines create | Fall back to CLI output with note |
| `gh pr review` fails | Error with stderr, still print CLI output |
| Finding has no line number | Post as file-level comment (omit `line` field) |
| Finding path not in PR diff | Skip that comment, warn in CLI output |

**Principle:** Never lose findings — if GitHub posting fails, always fall back to CLI output.

## Testing Strategy

### Unit Tests

`tests/skills/review_pr/test_github_review.py`:
- `test_build_review_payload_filters_by_severity`
- `test_build_review_payload_determines_event_type`
- `test_format_summary_counts_by_severity`
- `test_format_inline_comment_body`
- `test_finding_without_line_becomes_file_comment`

### Integration Tests (mocked subprocess)

- `test_detect_pr_for_branch_found`
- `test_detect_pr_for_branch_not_found`
- `test_post_review_success`
- `test_post_review_gh_failure_falls_back_to_cli`

### Manual Verification

Run `/review-pr --post` on actual PR to confirm comments appear correctly.

## Out of Scope

- Updating existing review comments (always creates new review)
- Deleting/editing posted comments
- Support for non-GitHub providers (GitLab, Bitbucket)
