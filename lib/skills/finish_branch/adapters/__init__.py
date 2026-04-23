"""Work item close adapters for finish-branch skill."""

from lib.skills.finish_branch.adapters.base import CloseAdapter, CloseResult
from lib.skills.finish_branch.adapters.github_issues import GitHubIssuesCloseAdapter
from lib.skills.finish_branch.adapters.jira import JiraCloseAdapter
from lib.skills.finish_branch.adapters.notion import NotionCloseAdapter
from lib.skills.finish_branch.adapters.noop import NoopCloseAdapter

__all__ = [
    "CloseAdapter",
    "CloseResult",
    "GitHubIssuesCloseAdapter",
    "JiraCloseAdapter",
    "NotionCloseAdapter",
    "NoopCloseAdapter",
]
