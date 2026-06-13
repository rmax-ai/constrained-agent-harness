"""Metrics helpers for run and experiment reporting."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from constrained_agent.domain.events import EventType
from constrained_agent.reporting.experiment_report import ExperimentReport


def compute_run_metrics(
    run: Any,
    candidates: Sequence[Any],
    events: Sequence[Any],
) -> dict[str, Any]:
    """Compute normalized per-run metrics from ORM-like records."""

    def event_name(event: Any) -> str:
        raw = event.event_type
        return str(raw.value if hasattr(raw, "value") else raw)

    declared_complete = any(
        event_name(event) == EventType.COMPLETION_DECLARED.value for event in events
    )
    verified_complete = getattr(run, "status", "") == "COMPLETED"
    hidden_failed = False
    final_evaluation: dict[str, Any] = {}
    if candidates:
        latest_evaluation = getattr(candidates[-1], "evaluation", None)
        if latest_evaluation is not None:
            final_evaluation = latest_evaluation.model_dump(mode="json")
            hidden_failed = (latest_evaluation.hidden_tests_failed or 0) > 0

    return {
        "run_id": run.id,
        "status": run.status,
        "declared_complete": declared_complete,
        "verified_complete": verified_complete,
        "hidden_tests_passed": verified_complete and not hidden_failed,
        "false_completion": declared_complete and not verified_complete,
        "policy_violations": sum(
            len(event.payload.get("violations", []))
            for event in events
            if event_name(event) == EventType.POLICY_CHECK.value
        ),
        "rollbacks": sum(
            1
            for event in events
            if event_name(event) == EventType.TRANSITION_DECIDED.value
            and event.payload.get("decision") == "ROLLBACK"
        ),
        "model_calls": sum(
            1 for event in events if event_name(event) == EventType.MODEL_CALL.value
        ),
        "token_usage": 0,
        "estimated_cost": 0.0,
        "duration": max(
            0.0,
            (run.updated_at - run.created_at).total_seconds(),
        ),
        "final_evaluation": final_evaluation,
    }


def compute_experiment_metrics(
    runs: Sequence[dict[str, Any]],
    mode: str = "unknown",
) -> ExperimentReport:
    """Aggregate per-run metric dictionaries into an experiment report."""
    repetitions = len(runs)
    declared_count = sum(1 for run in runs if bool(run.get("declared_complete")))
    verified_count = sum(1 for run in runs if bool(run.get("verified_complete")))
    declared_and_verified = sum(
        1
        for run in runs
        if bool(run.get("declared_complete")) and bool(run.get("verified_complete"))
    )
    hidden_success = sum(1 for run in runs if bool(run.get("hidden_tests_passed")))
    false_completion_count = sum(1 for run in runs if bool(run.get("false_completion")))

    return ExperimentReport(
        mode=mode,
        repetitions=repetitions,
        declared_completion_rate=_safe_rate(declared_count, repetitions),
        verified_completion_rate=_safe_rate(verified_count, repetitions),
        verified_completion_precision=_safe_rate(declared_and_verified, declared_count),
        hidden_test_success_rate=_safe_rate(hidden_success, repetitions),
        false_completion_count=false_completion_count,
        policy_violation_count=sum(int(run.get("policy_violations", 0)) for run in runs),
        rollback_count=sum(int(run.get("rollbacks", 0)) for run in runs),
        model_calls=sum(int(run.get("model_calls", 0)) for run in runs),
        token_usage=sum(int(run.get("token_usage", 0)) for run in runs),
        estimated_cost=sum(float(run.get("estimated_cost", 0.0)) for run in runs),
        wall_clock_duration=sum(float(run.get("duration", 0.0)) for run in runs),
    )


def _safe_rate(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator
