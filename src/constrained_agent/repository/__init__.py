"""Repository store — Git-backed immutable state."""

from constrained_agent.repository.git_store import GitRepositoryStore
from constrained_agent.repository.protocol import RepositoryState, RepositoryStore
from constrained_agent.repository.worktree import (
    create_detached_worktree,
    is_worktree_clean,
    list_active_worktrees,
    remove_worktree,
)

__all__ = [
    "GitRepositoryStore",
    "RepositoryState",
    "RepositoryStore",
    "create_detached_worktree",
    "is_worktree_clean",
    "list_active_worktrees",
    "remove_worktree",
]
