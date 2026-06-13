from __future__ import annotations

from pathlib import Path

from constrained_agent.agents.protocol import AgentProposal, ProposedCommand
from constrained_agent.domain import ApprovalGate, GoalContract
from constrained_agent.policy import PolicyEngine


def make_contract(
    *,
    writable_paths: list[str] | None = None,
    protected_paths: list[str] | None = None,
    allowed_commands: list[list[str]] | None = None,
    forbidden_patterns: list[str] | None = None,
    approval_gates: list[str] | None = None,
    dependency_policy: str = "frozen",
    max_runtime_seconds: int = 60,
) -> GoalContract:
    return GoalContract.model_validate(
        {
            "schema_version": "1",
            "task": {
                "id": "task-1",
                "title": "Task",
                "description": "Description",
            },
            "model": {
                "provider": "test",
                "name": "stub",
                "temperature": 0.0,
            },
            "acceptance": {
                "required_checks": [],
                "hidden_checks": None,
            },
            "constraints": {
                "max_iterations": 3,
                "max_runtime_seconds": max_runtime_seconds,
                "max_model_calls": 5,
                "writable_paths": writable_paths or ["src/**", "tests/**"],
                "protected_paths": protected_paths or [],
                "allowed_commands": allowed_commands or [["uv"], ["pytest"]],
                "forbidden_patterns": forbidden_patterns or [],
                "network_mode": "off",
                "dependency_policy": dependency_policy,
            },
            "approval_gates": approval_gates or [],
            "termination": {
                "success_conditions": [],
                "failure_conditions": [],
            },
            "experiment": {
                "context_strategy": "full",
                "completion_strategy": "controller_decides",
                "checkpoint_strategy": "per_iteration",
                "branching_factor": 1,
            },
        }
    )


def test_path_traversal_attempts_are_rejected(tmp_path: Path) -> None:
    engine = PolicyEngine(make_contract())
    proposal = AgentProposal(write_files=["../outside.txt"])

    report = engine.check_proposal(proposal, tmp_path)

    assert report.allowed is False
    assert "path traversal rejected: ../outside.txt" in report.violations


def test_protected_file_edits_are_blocked(tmp_path: Path) -> None:
    engine = PolicyEngine(
        make_contract(
            writable_paths=["src/**", "tests/**"],
            protected_paths=["tests/**"],
            approval_gates=[ApprovalGate.SENSITIVE_FILE_CHANGE.value],
        )
    )
    proposal = AgentProposal(write_files=["tests/unit/test_policy_engine.py"])

    report = engine.check_proposal(proposal, tmp_path)

    assert report.allowed is False
    assert "tests/unit/test_policy_engine.py" in report.protected_file_attempts
    assert ApprovalGate.SENSITIVE_FILE_CHANGE in report.requires_approval


def test_allowed_commands_pass_through(tmp_path: Path) -> None:
    engine = PolicyEngine(make_contract())
    proposal = AgentProposal(
        commands=[ProposedCommand(argv=["uv", "run", "pytest", "tests/unit"], timeout_seconds=30)]
    )

    report = engine.check_proposal(proposal, tmp_path)

    assert report.allowed is True
    assert report.violations == []
    assert report.rejected_commands == []


def test_forbidden_patterns_are_caught(tmp_path: Path) -> None:
    engine = PolicyEngine(make_contract(forbidden_patterns=["rm -rf", "curl"]))
    proposal = AgentProposal(
        commands=[ProposedCommand(argv=["uv", "run", "curl", "https://example.com"])]
    )

    report = engine.check_proposal(proposal, tmp_path)

    assert report.allowed is False
    assert report.rejected_commands == ["uv run curl https://example.com"]
    assert any("forbidden pattern" in violation for violation in report.violations)


def test_dependency_changes_detected(tmp_path: Path) -> None:
    engine = PolicyEngine(make_contract(approval_gates=[ApprovalGate.DEPENDENCY_CHANGE.value]))
    proposal = AgentProposal(
        diff=(
            "diff --git a/pyproject.toml b/pyproject.toml\n"
            "--- a/pyproject.toml\n"
            "+++ b/pyproject.toml\n"
            "@@ -1,3 +1,4 @@\n"
            '+httpx = ">=0.28"\n'
        )
    )

    report = engine.check_proposal(proposal, tmp_path)

    assert report.allowed is False
    assert "dependency changes are forbidden by the contract" in report.violations
    assert ApprovalGate.DEPENDENCY_CHANGE in report.requires_approval
    assert report.details["dependency_change_detected"] is True
