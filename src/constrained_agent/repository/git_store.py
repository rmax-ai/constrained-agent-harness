"""Git-backed repository store implementation."""

from __future__ import annotations

import subprocess
from pathlib import Path
from uuid import UUID

from constrained_agent.errors import RepositoryStateError
from constrained_agent.repository.protocol import RepositoryState, RepositoryStore


class GitRepositoryStore(RepositoryStore):
    """Manage isolated repository state transitions in a run workspace."""

    def __init__(self, *, runtime_dir: Path, run_id: UUID | str) -> None:
        self._run_root = runtime_dir / "runs" / str(run_id)
        self._workspace = self._run_root / "workspace"
        self._source: Path | None = None
        self._created_iteration = 0

    @property
    def workspace(self) -> Path:
        """Return the isolated workspace path."""
        return self._workspace

    def initialize(self, source: Path) -> RepositoryState:
        """Clone a clean source repository into the run workspace."""
        source_path = source.resolve()
        self._assert_git_repository(source_path)
        self._assert_clean(source_path)
        if self._workspace.exists():
            raise RepositoryStateError(f"workspace already exists: {self._workspace}")

        self._workspace.parent.mkdir(parents=True, exist_ok=True)
        self._run_git(
            source_path.parent,
            ["clone", "--no-hardlinks", str(source_path), str(self._workspace)],
        )
        self._run_git(self._workspace, ["config", "user.name", "CAH Workspace"])
        self._run_git(self._workspace, ["config", "user.email", "cah-workspace@example.com"])
        self._source = source_path
        self._created_iteration = 0
        return self._capture_state(created_iteration=0)

    def checkpoint(self, message: str) -> RepositoryState:
        """Commit all workspace changes and return the new repository state."""
        self._ensure_initialized()
        self._assert_clean_index_for_commit_message(message)
        if self._is_clean():
            raise RepositoryStateError("cannot checkpoint a clean workspace")

        self._run_git(self._workspace, ["add", "--all"])
        self._run_git(self._workspace, ["commit", "-m", message])
        self._created_iteration += 1
        return self._capture_state(created_iteration=self._created_iteration)

    def restore(self, state: RepositoryState) -> None:
        """Restore the isolated workspace to a specific commit."""
        self._ensure_initialized()
        self._assert_known_commit(state.commit_sha)
        self._run_git(self._workspace, ["reset", "--hard", state.commit_sha])
        self._run_git(self._workspace, ["clean", "-fd"])

    def diff(self, before: RepositoryState, after: RepositoryState) -> str:
        """Return a patch diff between two repository commits."""
        self._ensure_initialized()
        self._assert_known_commit(before.commit_sha)
        self._assert_known_commit(after.commit_sha)
        result = self._run_git(self._workspace, ["diff", before.commit_sha, after.commit_sha])
        return result.stdout

    def create_branch(self, state: RepositoryState, name: str) -> RepositoryState:
        """Create or replace a branch at a specific commit and check it out."""
        self._ensure_initialized()
        self._assert_known_commit(state.commit_sha)
        self._run_git(self._workspace, ["checkout", "-B", name, state.commit_sha])
        return self._capture_state(created_iteration=state.created_iteration)

    def _capture_state(self, *, created_iteration: int) -> RepositoryState:
        commit_sha = self._git_output(["rev-parse", "HEAD"])
        parent_sha = self._optional_git_output(["rev-parse", "HEAD^"])
        branch_name = self._git_output(["rev-parse", "--abbrev-ref", "HEAD"])
        tree_hash = self._git_output(["rev-parse", "HEAD^{tree}"])
        diff_statistics = self._diff_statistics(parent_sha, commit_sha)
        return RepositoryState(
            commit_sha=commit_sha,
            parent_sha=parent_sha,
            branch_name=branch_name,
            tree_hash=tree_hash,
            diff_statistics=diff_statistics,
            evaluation_ref=None,
            created_iteration=created_iteration,
        )

    def _diff_statistics(
        self, parent_sha: str | None, commit_sha: str
    ) -> dict[str, int | str] | None:
        if parent_sha is None:
            return None
        result = self._run_git(
            self._workspace,
            ["diff", "--shortstat", parent_sha, commit_sha],
        )
        summary = result.stdout.strip()
        if summary == "":
            return {
                "files_changed": 0,
                "insertions": 0,
                "deletions": 0,
                "summary": "",
            }

        files_changed = 0
        insertions = 0
        deletions = 0
        for part in summary.split(","):
            stripped = part.strip()
            if "file changed" in stripped or "files changed" in stripped:
                files_changed = int(stripped.split()[0])
            elif "insertion" in stripped:
                insertions = int(stripped.split()[0])
            elif "deletion" in stripped:
                deletions = int(stripped.split()[0])
        return {
            "files_changed": files_changed,
            "insertions": insertions,
            "deletions": deletions,
            "summary": summary,
        }

    def _assert_git_repository(self, path: Path) -> None:
        if not (path / ".git").exists():
            raise RepositoryStateError(f"not a git repository: {path}")

    def _assert_clean(self, repository: Path) -> None:
        result = self._run_git(repository, ["status", "--porcelain"])
        if result.stdout.strip():
            raise RepositoryStateError(
                "refusing to clone a repository with uncommitted changes; source state is ambiguous"
            )

    def _assert_clean_index_for_commit_message(self, message: str) -> None:
        if message.strip() == "":
            raise RepositoryStateError("checkpoint message must not be empty")

    def _ensure_initialized(self) -> None:
        if self._source is None or not self._workspace.exists():
            raise RepositoryStateError("repository store has not been initialized")

    def _is_clean(self) -> bool:
        result = self._run_git(self._workspace, ["status", "--porcelain"])
        return result.stdout.strip() == ""

    def _assert_known_commit(self, commit_sha: str) -> None:
        self._run_git(self._workspace, ["cat-file", "-e", f"{commit_sha}^{{commit}}"])

    def _git_output(self, args: list[str]) -> str:
        result = self._run_git(self._workspace, args)
        return result.stdout.strip()

    def _optional_git_output(self, args: list[str]) -> str | None:
        try:
            return self._git_output(args)
        except RepositoryStateError:
            return None

    def _run_git(self, cwd: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
        try:
            return subprocess.run(
                ["git", *args],
                cwd=cwd,
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as exc:
            stderr = exc.stderr.strip() if exc.stderr else "unknown git failure"
            raise RepositoryStateError(stderr) from exc
