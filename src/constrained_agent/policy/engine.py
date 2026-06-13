"""Policy engine orchestration across path, command, and dependency checks."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from constrained_agent.agents.protocol import AgentProposal
from constrained_agent.domain.approvals import ApprovalGate
from constrained_agent.domain.contracts import DependencyPolicy as DependencyMode
from constrained_agent.domain.contracts import GoalContract
from constrained_agent.policy.commands import CommandPolicy
from constrained_agent.policy.dependencies import DependencyPolicy
from constrained_agent.policy.paths import PathPolicy


class PolicyReport(BaseModel):
    """Structured result of validating an agent proposal."""

    model_config = ConfigDict(extra="forbid")

    allowed: bool
    violations: list[str] = Field(default_factory=list)
    protected_file_attempts: list[str] = Field(default_factory=list)
    rejected_commands: list[str] = Field(default_factory=list)
    requires_approval: list[ApprovalGate] = Field(default_factory=list)
    details: dict[str, Any] = Field(default_factory=dict)


class PolicyEngine:
    """Apply contract-backed policy checks to a proposal."""

    def __init__(self, contract: GoalContract) -> None:
        self._contract = contract
        allowed_commands = [
            Path(command[0]).name for command in contract.constraints.allowed_commands if command
        ]
        self._path_policy = PathPolicy(
            writable_paths=contract.constraints.writable_paths,
            protected_paths=contract.constraints.protected_paths,
        )
        self._command_policy = CommandPolicy(
            allowed_commands=allowed_commands,
            forbidden_patterns=contract.constraints.forbidden_patterns,
        )
        self._dependency_policy = DependencyPolicy(
            allow_changes=contract.constraints.dependency_policy is not DependencyMode.FROZEN
        )
        self._enabled_approval_gates = {
            ApprovalGate(gate_name) for gate_name in contract.approval_gates
        }

    def check_proposal(self, proposal: AgentProposal, workspace: Path) -> PolicyReport:
        """Run all sub-policies and return a comprehensive report."""
        violations: list[str] = []
        protected_file_attempts: list[str] = []
        rejected_commands: list[str] = []
        required_approvals: list[ApprovalGate] = []
        workspace_root = workspace.resolve(strict=False)

        for raw_path in proposal.write_files:
            path = Path(raw_path)
            resolved = self._path_policy.resolve(path, workspace_root)
            if ".." in path.parts or self._path_policy.reject_path_traversal(resolved):
                violations.append(f"path traversal rejected: {raw_path}")
                continue
            if self._path_policy.reject_symlink_escape(resolved):
                violations.append(f"symlink escape rejected: {raw_path}")
                continue

            relative_path = resolved.relative_to(workspace_root)
            normalized_path = relative_path.as_posix()
            if self._path_policy.is_protected(relative_path):
                protected_file_attempts.append(normalized_path)
                violations.append(f"protected path modification blocked: {normalized_path}")
                if ApprovalGate.SENSITIVE_FILE_CHANGE in self._enabled_approval_gates:
                    required_approvals.append(ApprovalGate.SENSITIVE_FILE_CHANGE)
                continue
            if not self._path_policy.is_writable(relative_path):
                violations.append(f"path is not writable: {normalized_path}")

        for command in proposal.commands:
            if self._command_policy.reject_shell_strings(command):
                rejected_commands.append(str(command.argv))
                violations.append("shell-string commands are forbidden")
                continue

            argv = command.argv
            if not isinstance(argv, list):
                rejected_commands.append(str(argv))
                violations.append("commands must be argument arrays")
                continue
            if not self._command_policy.is_allowed(argv):
                rejected_commands.append(" ".join(argv))
                violations.append(f"command is not allowed: {argv[0]}")
                continue
            if self._command_policy.has_forbidden_pattern(argv):
                rejected_commands.append(" ".join(argv))
                violations.append(f"command matches forbidden pattern: {' '.join(argv)}")

        if not self._command_policy.all_timeouts_within_limit(
            proposal.commands,
            self._contract.constraints.max_runtime_seconds,
        ):
            violations.append("one or more command timeouts exceed max_runtime_seconds")

        dependency_change = self._dependency_policy.check_dependency_changes(proposal.diff)
        dependency_gate = self._dependency_policy.requires_approval(proposal.diff)
        if dependency_change and not self._dependency_policy.allow_changes:
            violations.append("dependency changes are forbidden by the contract")
        if (
            dependency_gate is not None
            and dependency_gate in self._enabled_approval_gates
            and dependency_gate not in required_approvals
        ):
            required_approvals.append(dependency_gate)

        allowed = not violations and not required_approvals
        return PolicyReport(
            allowed=allowed,
            violations=violations,
            protected_file_attempts=protected_file_attempts,
            rejected_commands=rejected_commands,
            requires_approval=required_approvals,
            details={
                "workspace": str(workspace_root),
                "dependency_change_detected": dependency_change,
                "writable_paths": list(self._contract.constraints.writable_paths),
                "protected_paths": list(self._contract.constraints.protected_paths),
            },
        )
