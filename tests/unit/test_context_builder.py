from __future__ import annotations

import subprocess
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from constrained_agent.context import ContextBuilder
from constrained_agent.context.repository_map import RepositoryMap
from constrained_agent.context.token_budget import TokenBudget
from constrained_agent.domain import (
    Candidate,
    CandidateStatus,
    EvaluationResult,
    EvaluationTier,
    EvaluationVector,
    Evidence,
    GoalContract,
    Run,
    RunStatus,
)


def _run_git(repository: Path, args: list[str]) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _make_contract() -> GoalContract:
    return GoalContract.model_validate(
        {
            "schema_version": "1",
            "task": {
                "id": "task-ctx",
                "title": "Fix failing webhook test",
                "description": "Rebuild context for the next model call.",
            },
            "model": {"provider": "test", "name": "stub", "temperature": 0.0},
            "acceptance": {"required_checks": [], "hidden_checks": None},
            "constraints": {
                "max_iterations": 5,
                "max_runtime_seconds": 120,
                "max_model_calls": 8,
                "writable_paths": ["src/", "tests/unit/"],
                "protected_paths": ["tests/protected/"],
                "allowed_commands": [["uv", "run", "pytest"]],
                "forbidden_patterns": [],
                "network_mode": "off",
                "dependency_policy": "frozen",
            },
            "approval_gates": [],
            "termination": {"success_conditions": [], "failure_conditions": []},
            "experiment": {
                "context_strategy": "full",
                "completion_strategy": "controller_decides",
                "checkpoint_strategy": "per_iteration",
                "branching_factor": 1,
            },
        }
    )


class FakeRepositoryStore:
    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace


def _create_workspace(tmp_path: Path) -> tuple[Path, str]:
    workspace = tmp_path / "workspace"
    (workspace / "src/constrained_agent").mkdir(parents=True)
    (workspace / "tests/unit").mkdir(parents=True)
    _run_git(tmp_path, ["init", "-b", "main", str(workspace)])
    _run_git(workspace, ["config", "user.name", "CAH Test"])
    _run_git(workspace, ["config", "user.email", "cah@example.com"])

    (workspace / "src/constrained_agent/webhook.py").write_text(
        "from constrained_agent.database import save_event\n\n"
        "def process_webhook(payload: dict) -> None:\n"
        "    save_event(payload)\n",
        encoding="utf-8",
    )
    (workspace / "src/constrained_agent/database.py").write_text(
        "def save_event(payload: dict) -> None:\n"
        "    _ = payload\n",
        encoding="utf-8",
    )
    (workspace / "tests/unit/test_webhook.py").write_text(
        "from constrained_agent.webhook import process_webhook\n\n"
        "def test_webhook_handles_payload() -> None:\n"
        "    process_webhook({'id': '1'})\n",
        encoding="utf-8",
    )
    _run_git(workspace, ["add", "."])
    _run_git(workspace, ["commit", "-m", "initial"])

    (workspace / "src/constrained_agent/webhook.py").write_text(
        "from constrained_agent.database import save_event\n\n"
        "def process_webhook(payload: dict) -> None:\n"
        "    if 'id' not in payload:\n"
        "        raise ValueError('missing id')\n"
        "    save_event(payload)\n",
        encoding="utf-8",
    )
    head_sha = _run_git(workspace, ["rev-parse", "HEAD"])
    return workspace, head_sha


async def test_context_builder_produces_valid_agent_context(tmp_path: Path) -> None:
    workspace, head_sha = _create_workspace(tmp_path)
    builder = ContextBuilder(
        _make_contract(),
        FakeRepositoryStore(workspace),
        max_chars_per_file=120,
        max_files=3,
        max_diff_size=160,
        max_failure_records=5,
    )
    run = Run(
        id=uuid4(),
        status=RunStatus.ACTIVE,
        goal_hash="a" * 64,
        initial_commit=head_sha,
        experiment_mode="controller_decides",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        metadata={
            "budget_usage": {
                "iterations_consumed": 1,
                "model_calls": 2,
                "runtime_seconds": 12.5,
                "sandbox_seconds": 3.0,
            }
        },
    )
    candidate = Candidate(
        id=uuid4(),
        repository_state_hash=head_sha,
        evaluation=EvaluationVector(visible_tests_failed=1),
        parent_id=None,
        depth=1,
        status=CandidateStatus.REJECTED,
        iteration=1,
        created_at=datetime.now(UTC),
    )
    evidence = [
        Evidence(
            id=uuid4(),
            run_id=run.id,
            iteration=1,
            candidate_id=candidate.id,
            event_type="TRANSITION_DECIDED",
            payload={
                "decision": "REJECT",
                "summary": "Tried changing database writes before understanding the failing webhook path.",
                "evaluation_results": [
                    EvaluationResult(
                        evaluator_id="pytest",
                        tier=EvaluationTier.TIER_2_TARGETED_TESTS,
                        passed=False,
                        stdout="",
                        stderr="AssertionError: process_webhook should reject malformed payloads",
                        exit_code=1,
                        duration_seconds=0.8,
                    ).model_dump(mode="json")
                ],
            },
            artifact_refs=[],
            timestamp=datetime.now(UTC),
        )
    ]
    stagnation_report = {
        "failing_tests": ["tests/unit/test_webhook.py"],
        "search_patterns": ["process_webhook", "src/constrained_agent/webhook.py:4"],
    }

    context = await builder.build(run, candidate, evidence, stagnation_report)

    assert context.goal_summary.startswith("Fix failing webhook test:")
    assert "workspace/" in context.repository_map
    assert "Relevant files:" in context.repository_map
    assert "process_webhook" in context.repository_map
    assert len(context.candidate_diff) <= 160
    assert "tier_2_targeted_tests" in context.evaluation_failures
    assert "iterations left" in context.remaining_budget
    assert context.permitted_actions
    assert context.protected_summary == "tests/protected/"
    assert context.iteration == 2
    assert "Context manifest" in builder.last_manifest


def test_repository_map_handles_missing_directories(tmp_path: Path) -> None:
    missing = tmp_path / "missing"
    repository_map = RepositoryMap(missing)

    assert repository_map.build(missing) == "missing/ (missing)"
    assert repository_map.find_relevant_files(["tests/unit/test_missing.py"], ["missing"]) == []


def test_truncation_respects_limits() -> None:
    text = "a" * 40
    truncated = TokenBudget.truncate_to_budget(text, max_tokens=5)

    assert truncated.endswith("...")
    assert len(truncated) <= 20


def test_token_estimation_is_reasonable() -> None:
    assert TokenBudget.estimate_tokens("") == 0
    assert TokenBudget.estimate_tokens("abcd") == 1
    assert TokenBudget.estimate_tokens("a" * 17) == 5
