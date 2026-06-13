from __future__ import annotations

from constrained_agent.domain import (
    BudgetTracker,
    EvaluationVector,
    GoalContract,
)


def make_contract(*, max_iterations: int = 3, max_runtime_seconds: int = 60) -> GoalContract:
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
                "max_iterations": max_iterations,
                "max_runtime_seconds": max_runtime_seconds,
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


def test_evaluation_vector_prefers_hard_gates_before_test_counts() -> None:
    safer = EvaluationVector(
        policy_violations=0,
        protected_file_changes=0,
        security_critical=0,
        visible_tests_passed=1,
    )
    riskier = EvaluationVector(
        policy_violations=1,
        protected_file_changes=0,
        security_critical=0,
        visible_tests_passed=100,
    )

    assert safer.is_better_than(riskier) is True
    assert riskier.is_better_than(safer) is False


def test_evaluation_vector_prefers_successful_blocking_checks() -> None:
    compiled = EvaluationVector(compilation_ok=True)
    unknown = EvaluationVector(compilation_ok=None)

    assert compiled.is_better_than(unknown) is True
    assert unknown.is_better_than(compiled) is False


def test_evaluation_vector_checks_acceptability_against_contract() -> None:
    contract = make_contract()

    acceptable = EvaluationVector(
        visible_tests_passed=3,
        runtime_seconds=5.0,
    )
    unacceptable = EvaluationVector(
        dependency_changes=1,
        runtime_seconds=5.0,
    )

    assert acceptable.is_acceptable(contract) is True
    assert unacceptable.is_acceptable(contract) is False


def test_budget_tracker_reports_reserved_remaining_and_exceeded() -> None:
    tracker = BudgetTracker(make_contract(max_iterations=1, max_runtime_seconds=60))

    tracker.record_iteration()
    tracker.record_iteration()
    tracker.record_model_call(10, 5)
    tracker.record_sandbox_time(2.5)

    reserved = tracker.reserved()
    remaining = tracker.remaining()

    assert reserved.iterations_consumed == 1
    assert reserved.model_calls == 5
    assert reserved.runtime_seconds == 60.0
    assert remaining.iterations_consumed == 0
    assert remaining.model_calls == 4
    assert tracker.exceeded() == ["iterations_consumed"]


def test_budget_tracker_rejects_negative_measurements() -> None:
    tracker = BudgetTracker(make_contract())

    try:
        tracker.record_model_call(-1, 0)
    except ValueError as exc:
        assert "non-negative" in str(exc)
    else:
        raise AssertionError("expected ValueError for negative token count")

    try:
        tracker.record_sandbox_time(-0.1)
    except ValueError as exc:
        assert "non-negative" in str(exc)
    else:
        raise AssertionError("expected ValueError for negative sandbox time")
