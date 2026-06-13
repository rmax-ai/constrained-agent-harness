"""Command policy checks for agent proposals."""

from __future__ import annotations

from pathlib import Path
from typing import Any


class CommandPolicy:
    """Validate structured command proposals against contract constraints."""

    def __init__(self, allowed_commands: list[str], forbidden_patterns: list[str]) -> None:
        self._allowed_commands = {
            command.strip() for command in allowed_commands if command.strip()
        }
        self._forbidden_patterns = [pattern.strip().lower() for pattern in forbidden_patterns]

    def is_allowed(self, argv: list[str]) -> bool:
        """Return whether the command basename is on the allowlist."""
        if not argv or not self._allowed_commands:
            return False
        return Path(argv[0]).name in self._allowed_commands

    def has_forbidden_pattern(self, argv: list[str]) -> bool:
        """Return whether the argv sequence matches a forbidden pattern."""
        command_text = " ".join(argv).lower()
        return any(pattern in command_text for pattern in self._forbidden_patterns)

    def reject_shell_strings(self, proposal_command: Any) -> bool:
        """Reject shell-string commands; only argv arrays are permitted."""
        if isinstance(proposal_command, str):
            return True
        if isinstance(proposal_command, list):
            return False
        argv = getattr(proposal_command, "argv", None)
        if isinstance(argv, str):
            return True
        return not isinstance(argv, list)

    def all_timeouts_within_limit(self, commands: list[Any], max_timeout: int) -> bool:
        """Return whether all proposed command timeouts fit within the contract."""
        for command in commands:
            if isinstance(command, dict):
                timeout = command.get("timeout_seconds", 0)
            else:
                timeout = getattr(command, "timeout_seconds", 0)
            if timeout > max_timeout:
                return False
        return True
