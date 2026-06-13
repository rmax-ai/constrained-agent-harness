from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from constrained_agent.domain import (
    Approval,
    ApprovalGate,
    ApprovalStatus,
    BudgetTracker,
    ContractValidator,
    EvaluationVector,
    Event,
    EventType,
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


def test_contract_validation_detects_duplicate_required_check_ids() -> None:
    contract = GoalContract.model_validate(
        {
            **make_contract().model_dump(mode="json"),
            "acceptance": {
                "required_checks": [
                    {
                        "id": "dup",
                        "evaluator": "pytest",
                        "command": ["uv", "run", "pytest"],
                    },
                    {
                        "id": "dup",
                        "evaluator": "pytest",
                        "command": ["uv", "run", "pytest", "-q"],
                    },
                ],
                "hidden_checks": None,
            },
        }
    )

    errors = ContractValidator.validate(contract)

    assert errors
    assert "duplicate id 'dup'" in errors[0]


def test_budget_tracking_reports_remaining_budget() -> None:
    tracker = BudgetTracker(make_contract(max_iterations=2, max_runtime_seconds=60))

    tracker.record_iteration()
    tracker.record_model_call(10, 4)
    tracker.record_sandbox_time(1.25)
    remaining = tracker.remaining()

    assert remaining.iterations_consumed == 1
    assert remaining.model_calls == 4
    assert tracker.exceeded() == []


def test_evaluation_vector_comparison_prefers_fewer_failures() -> None:
    stronger = EvaluationVector(visible_tests_passed=5, visible_tests_failed=0)
    weaker = EvaluationVector(visible_tests_passed=50, visible_tests_failed=1)

    assert stronger.is_better_than(weaker) is True
    assert weaker.is_better_than(stronger) is False


def test_approval_model_validates_required_fields() -> None:
    approval = Approval(
        id=uuid4(),
        run_id=uuid4(),
        gate=ApprovalGate.DEPENDENCY_CHANGE,
        description="Add a new runtime dependency",
        details={"package": "hypothesis"},
        status=ApprovalStatus.PENDING,
        created_at=datetime.now(UTC),
        decided_at=None,
        decided_by=None,
    )

    assert approval.status is ApprovalStatus.PENDING
    assert approval.details["package"] == "hypothesis"


def test_event_hash_changes_when_previous_hash_changes() -> None:
    event = Event(
        id=uuid4(),
        run_id=uuid4(),
        event_type=EventType.RUN_CREATED,
        iteration=0,
        source_state=None,
        target_state="CREATED",
        payload={"message": "created"},
        previous_event_hash=None,
        event_hash="placeholder",
        timestamp=datetime.now(UTC),
    )

    first_hash = Event.compute_hash(event, None)
    second_hash = Event.compute_hash(event, "previous")

    assert first_hash != second_hash


def test_event_rejects_negative_iteration() -> None:
    with pytest.raises(ValidationError):
        Event(
            id=uuid4(),
            run_id=uuid4(),
            event_type=EventType.RUN_CREATED,
            iteration=-1,
            source_state=None,
            target_state="CREATED",
            payload={},
            previous_event_hash=None,
            event_hash="placeholder",
            timestamp=datetime.now(UTC),
        )
