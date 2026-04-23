"""Work item close adapters for finish-branch skill."""

from lib.skills.finish_branch.adapters.base import CloseAdapter, CloseResult
from lib.skills.finish_branch.adapters.github_issues import GitHubIssuesCloseAdapter

__all__ = ["CloseAdapter", "CloseResult", "GitHubIssuesCloseAdapter"]
