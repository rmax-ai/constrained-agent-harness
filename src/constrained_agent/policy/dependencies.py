"""Dependency change detection and approval gating."""

from __future__ import annotations

import re

from constrained_agent.domain.approvals import ApprovalGate

_DEPENDENCY_FILE_PATTERN = re.compile(
    r"(^|/)(pyproject\.toml|uv\.lock|requirements(?:\.[^/\s]+)?\.txt|"
    r"poetry\.lock|Pipfile(?:\.lock)?|setup\.py|setup\.cfg)$"
)


class DependencyPolicy:
    """Detect dependency manifest changes in a proposed diff."""

    def __init__(self, allow_changes: bool) -> None:
        self._allow_changes = allow_changes

    def check_dependency_changes(self, diff_output: str) -> bool:
        """Return whether a diff touches a known dependency file."""
        for line in diff_output.splitlines():
            if line.startswith(("diff --git ", "+++ ", "--- ")):
                for token in line.split():
                    normalized = token.removeprefix("a/").removeprefix("b/")
                    if _DEPENDENCY_FILE_PATTERN.search(normalized):
                        return True
        return False

    def requires_approval(self, diff_output: str) -> ApprovalGate | None:
        """Return the approval gate for dependency changes when applicable."""
        if self.check_dependency_changes(diff_output):
            return ApprovalGate.DEPENDENCY_CHANGE
        return None

    @property
    def allow_changes(self) -> bool:
        """Expose whether dependency changes are permitted without violation."""
        return self._allow_changes
