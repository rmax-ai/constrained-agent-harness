"""Filesystem path policy checks for workspace-scoped edits."""

from __future__ import annotations

from fnmatch import fnmatch
from pathlib import Path


class PathPolicy:
    """Validate proposed file paths against writable and protected globs."""

    def __init__(self, writable_paths: list[str], protected_paths: list[str]) -> None:
        self._writable_paths = [self._normalize_pattern(path) for path in writable_paths]
        self._protected_paths = [self._normalize_pattern(path) for path in protected_paths]
        self._workspace_root: Path | None = None

    def is_writable(self, path: Path) -> bool:
        """Return whether a normalized path matches the writable glob set."""
        return self._matches(path, self._writable_paths)

    def is_protected(self, path: Path) -> bool:
        """Return whether a normalized path matches the protected glob set."""
        return self._matches(path, self._protected_paths)

    def reject_path_traversal(self, path: Path) -> bool:
        """Reject lexical traversal or any resolved path that escapes the workspace."""
        if ".." in path.parts:
            return True
        if self._workspace_root is None:
            return False
        return not self._is_within_workspace(path.resolve(strict=False))

    def reject_symlink_escape(self, path: Path) -> bool:
        """Reject symlinks whose resolved target escapes the workspace."""
        if self._workspace_root is None:
            return False
        if path.is_symlink():
            return not self._is_within_workspace(path.resolve(strict=False))
        return False

    def resolve(self, path: Path, base: Path) -> Path:
        """Resolve a path relative to the workspace root."""
        self._workspace_root = base.resolve(strict=False)
        candidate = path if path.is_absolute() else self._workspace_root / path
        return candidate.resolve(strict=False)

    def _matches(self, path: Path, patterns: list[str]) -> bool:
        normalized = self._normalize_path(path)
        return any(
            fnmatch(normalized, pattern) or normalized == pattern.rstrip("/")
            for pattern in patterns
        )

    def _normalize_path(self, path: Path) -> str:
        candidate = path.resolve(strict=False) if path.is_absolute() else path
        if self._workspace_root is not None and candidate.is_absolute():
            try:
                candidate = candidate.relative_to(self._workspace_root)
            except ValueError:
                return candidate.as_posix()
        normalized = candidate.as_posix().lstrip("./")
        return normalized or "."

    @staticmethod
    def _normalize_pattern(pattern: str) -> str:
        normalized = pattern.replace("\\", "/").lstrip("./")
        return normalized or "."

    def _is_within_workspace(self, path: Path) -> bool:
        if self._workspace_root is None:
            return False
        try:
            path.relative_to(self._workspace_root)
        except ValueError:
            return False
        return True
