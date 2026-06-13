from __future__ import annotations

from pathlib import Path

from constrained_agent.agents.protocol import AgentProposal, ProposedCommand
from constrained_agent.domain import GoalContract
from constrained_agent.policy import PolicyEngine


def _contract() -> GoalContract:
    return GoalContract.model_validate(
        {
            "schema_version": "1",
            "task": {"id": "task", "title": "task", "description": "task"},
            "model": {"provider": "test", "name": "scripted", "temperature": 0.0},
            "acceptance": {
                "required_checks": [
                    {
                        "id": "visible",
                        "evaluator": "pytest",
                        "command": ["python", "-V"],
                        "blocking": True,
                    }
                ],
                "hidden_checks": None,
            },
            "constraints": {
                "max_iterations": 2,
                "max_runtime_seconds": 30,
                "max_model_calls": 2,
                "writable_paths": ["src/**"],
                "protected_paths": ["tests/**"],
                "allowed_commands": [["python"], ["uv"]],
                "forbidden_patterns": ["curl", "wget"],
                "network_mode": "off",
                "dependency_policy": "frozen",
            },
            "approval_gates": [],
            "termination": {"success_conditions": ["x"], "failure_conditions": ["y"]},
            "experiment": {
                "context_strategy": "full",
                "completion_strategy": "controller_verified",
                "checkpoint_strategy": "per_iteration",
                "branching_factor": 1,
            },
        }
    )


def test_protected_file_modifications_are_rejected(tmp_path: Path) -> None:
    engine = PolicyEngine(_contract())
    proposal = AgentProposal(write_files=["tests/secret.py"])

    report = engine.check_proposal(proposal, tmp_path)

    assert report.allowed is False
    assert "tests/secret.py" in report.protected_file_attempts


def test_forbidden_commands_are_blocked(tmp_path: Path) -> None:
    engine = PolicyEngine(_contract())
    proposal = AgentProposal(
        commands=[ProposedCommand(argv=["python", "-c", "import os; os.system('curl x')"])]
    )

    report = engine.check_proposal(proposal, tmp_path)

    assert report.allowed is False
    assert report.rejected_commands == ["python -c import os; os.system('curl x')"]


def test_path_traversal_attempts_fail(tmp_path: Path) -> None:
    engine = PolicyEngine(_contract())
    proposal = AgentProposal(write_files=["../outside.py"])

    report = engine.check_proposal(proposal, tmp_path)

    assert report.allowed is False
    assert any("path traversal rejected" in violation for violation in report.violations)
