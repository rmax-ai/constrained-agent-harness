from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from constrained_agent.domain import EvaluationTier, GoalContract
from constrained_agent.evaluators import (
    CommandEvaluator,
    DiffSizeEvaluator,
    EvaluationContext,
    EvaluatorPipeline,
)
from constrained_agent.repository.protocol import RepositoryState
from constrained_agent.sandbox import ExecutionResult, FakeSandbox


def make_contract() -> GoalContract:
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
                "max_runtime_seconds": 60,
                "max_model_calls": 5,
                "writable_paths": [],
                "protected_paths": [],
                "allowed_commands": [],
                "forbidden_patterns": [],
                "network_mode": "off",
                "dependency_policy": "frozen",
            },
            "approval_gates": [],
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


def make_context(workspace: Path, sandbox: FakeSandbox | None = None) -> EvaluationContext:
    return EvaluationContext(
        workspace=workspace,
        repository_state=RepositoryState(
            commit_sha="abc123",
            parent_sha=None,
            branch_name="main",
            tree_hash="def456",
            diff_statistics=None,
            evaluation_ref=None,
            created_iteration=0,
        ),
        sandbox=sandbox,
        goal=make_contract(),
    )


@pytest.mark.asyncio
async def test_pipeline_runs_evaluators_in_tier_order_and_updates_vector(tmp_path) -> None:
    sandbox = FakeSandbox()
    sandbox.register(
        ["python", "-m", "compileall", "src"],
        ExecutionResult(stdout="", stderr="", exit_code=0, duration_seconds=0.2),
    )
    sandbox.register(
        ["uv", "run", "pytest", "tests/unit/test_example.py"],
        ExecutionResult(stdout="passed", stderr="", exit_code=0, duration_seconds=0.4),
    )
    pipeline = EvaluatorPipeline()
    pipeline.register(
        CommandEvaluator(
            evaluator_id="visible-tests",
            tier=EvaluationTier.TIER_2_TARGETED_TESTS,
            argv=["uv", "run", "pytest", "tests/unit/test_example.py"],
            purpose="run visible checks",
            outcome="visible_tests",
        )
    )
    pipeline.register(
        CommandEvaluator(
            evaluator_id="compile",
            tier=EvaluationTier.TIER_1_FAST_STATIC,
            argv=["python", "-m", "compileall", "src"],
            purpose="check compilation",
            outcome="compilation_ok",
        )
    )

    vector = await pipeline.evaluate(make_context(tmp_path, sandbox))

    assert vector.compilation_ok is True
    assert vector.visible_tests_passed == 1
    assert sandbox.requests[0].argv == ["python", "-m", "compileall", "src"]
    assert sandbox.requests[1].argv == ["uv", "run", "pytest", "tests/unit/test_example.py"]
    assert vector.runtime_seconds == pytest.approx(0.6)


@pytest.mark.asyncio
async def test_pipeline_short_circuits_after_tier_zero_failure(tmp_path) -> None:
    sandbox = FakeSandbox()
    sandbox.register(
        ["python", "-m", "safety_check"],
        ExecutionResult(stdout="", stderr="blocked", exit_code=1, duration_seconds=0.1),
    )
    sandbox.register(
        ["uv", "run", "pytest"],
        ExecutionResult(stdout="should not run", stderr="", exit_code=0, duration_seconds=0.3),
    )
    pipeline = EvaluatorPipeline()
    pipeline.register(
        CommandEvaluator(
            evaluator_id="policy-check",
            tier=EvaluationTier.TIER_0_POLICY,
            argv=["python", "-m", "safety_check"],
            purpose="run policy gate",
            outcome="policy_violations",
        )
    )
    pipeline.register(
        CommandEvaluator(
            evaluator_id="tests",
            tier=EvaluationTier.TIER_2_TARGETED_TESTS,
            argv=["uv", "run", "pytest"],
            purpose="run visible tests",
            outcome="visible_tests",
        )
    )

    vector = await pipeline.evaluate(make_context(tmp_path, sandbox))

    assert vector.policy_violations == 1
    assert vector.visible_tests_passed == 0
    assert len(sandbox.requests) == 1


@pytest.mark.asyncio
async def test_diff_size_evaluator_fails_when_limits_are_exceeded(tmp_path) -> None:
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True, text=True)
    subprocess.run(
        ["git", "config", "user.name", "Tests"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "tests@example.com"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    )
    file_path = tmp_path / "sample.txt"
    file_path.write_text("one\n", encoding="utf-8")
    subprocess.run(
        ["git", "add", "sample.txt"], cwd=tmp_path, check=True, capture_output=True, text=True
    )
    subprocess.run(
        ["git", "commit", "-m", "initial"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    )
    file_path.write_text("one\ntwo\nthree\n", encoding="utf-8")

    pipeline = EvaluatorPipeline()
    pipeline.register(DiffSizeEvaluator(max_added_lines=1))

    vector = await pipeline.evaluate(make_context(tmp_path, None))

    assert vector.policy_violations == 1
