"""Git worktree helpers used by the repository store."""

from __future__ import annotations

import subprocess
from pathlib import Path


def _run_git(repository: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    """Run a git command in a repository and return captured text output."""
    return subprocess.run(
        ["git", *args],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    )


def create_detached_worktree(repository: Path, target: Path, commit: str) -> Path:
    """Create a detached worktree rooted at a specific commit."""
    target.parent.mkdir(parents=True, exist_ok=True)
    _run_git(repository, ["worktree", "add", "--detach", str(target), commit])
    return target


def remove_worktree(repository: Path, target: Path, *, force: bool = False) -> None:
    """Remove a worktree and prune stale metadata."""
    args = ["worktree", "remove"]
    if force:
        args.append("--force")
    args.append(str(target))
    _run_git(repository, args)
    _run_git(repository, ["worktree", "prune"])


def is_worktree_clean(worktree: Path) -> bool:
    """Return whether a worktree has no tracked or untracked changes."""
    result = _run_git(worktree, ["status", "--porcelain"])
    return result.stdout.strip() == ""


def list_active_worktrees(repository: Path) -> list[Path]:
    """List paths for active worktrees registered in a repository."""
    result = _run_git(repository, ["worktree", "list", "--porcelain"])
    worktrees: list[Path] = []
    for line in result.stdout.splitlines():
        if line.startswith("worktree "):
            worktrees.append(Path(line.removeprefix("worktree ").strip()))
    return worktrees
