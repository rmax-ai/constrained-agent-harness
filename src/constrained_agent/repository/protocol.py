"""Repository store contracts for immutable Git-backed state."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field


class RepositoryState(BaseModel):
    """A concrete repository snapshot captured in Git."""

    model_config = ConfigDict(extra="forbid")

    commit_sha: str = Field(min_length=1)
    parent_sha: str | None = None
    branch_name: str = Field(min_length=1)
    tree_hash: str = Field(min_length=1)
    diff_statistics: dict[str, int | str] | None = None
    evaluation_ref: str | None = None
    created_iteration: int = Field(ge=0)


class RepositoryStore(Protocol):
    """Protocol for cloning, checkpointing, and restoring repository states."""

    def initialize(self, source: Path) -> RepositoryState:
        """Clone a source repository into an isolated workspace."""

    def checkpoint(self, message: str) -> RepositoryState:
        """Commit all staged and unstaged changes in the workspace."""

    def restore(self, state: RepositoryState) -> None:
        """Restore the isolated workspace to a previously captured state."""

    def diff(self, before: RepositoryState, after: RepositoryState) -> str:
        """Return the textual diff between two repository states."""

    def create_branch(self, state: RepositoryState, name: str) -> RepositoryState:
        """Create or move a branch reference to a captured state."""
