"""Run-level reporting models and serializers."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from constrained_agent.artifacts import CompletionManifest
from constrained_agent.domain.budgets import BudgetUsage
from constrained_agent.persistence.models import EvaluationModel, EventModel, RunModel


class RunReport(BaseModel):
    """Normalized report payload for a single persisted run."""

    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(min_length=1)
    status: str = Field(min_length=1)
    model: str = Field(min_length=1)
    goal_hash: str = Field(min_length=1)
    iterations: int = Field(ge=0)
    checkpoints: int = Field(ge=0)
    final_evaluation: dict[str, Any] = Field(default_factory=dict)
    budget: dict[str, Any] = Field(default_factory=dict)
    duration: float | None = Field(default=None, ge=0.0)
    completion_manifest_ref: str | None = None

    @classmethod
    def from_parts(
        cls,
        run: RunModel,
        events: list[EventModel],
        evaluations: list[EvaluationModel],
        manifest: CompletionManifest | None,
        *,
        completion_manifest_ref: str | None = None,
    ) -> RunReport:
        """Build a run report from persisted ORM models."""
        final_evaluation: dict[str, Any] = {}
        if evaluations:
            final_evaluation = dict(evaluations[-1].vector)
        elif manifest is not None:
            final_evaluation = dict(manifest.final_evaluation_vector)

        model_name = "unknown"
        if manifest is not None:
            model_name = f"{manifest.model_provider}:{manifest.model_identifier}"

        budget: dict[str, Any]
        if manifest is not None:
            budget = manifest.budget_usage.model_dump(mode="json")
        else:
            budget = _budget_from_events(events)

        duration = _duration_seconds(run.created_at, run.updated_at)
        iterations = max((event.iteration for event in events), default=0)
        checkpoints = sum(1 for event in events if event.event_type == "CHECKPOINT_CREATED")

        return cls(
            run_id=run.id,
            status=run.status,
            model=model_name,
            goal_hash=run.goal_hash,
            iterations=iterations,
            checkpoints=checkpoints,
            final_evaluation=final_evaluation,
            budget=budget,
            duration=duration,
            completion_manifest_ref=completion_manifest_ref,
        )


def generate_markdown_report(
    run: RunModel,
    events: list[EventModel],
    evaluations: list[EvaluationModel],
    manifest: CompletionManifest | None,
) -> str:
    """Render a human-readable markdown run report."""
    report = RunReport.from_parts(
        run,
        events,
        evaluations,
        manifest,
        completion_manifest_ref=_completion_manifest_ref(events, manifest),
    )
    lines = [
        f"# Run Report: {report.run_id}",
        "",
        f"- Status: `{report.status}`",
        f"- Model: `{report.model}`",
        f"- Goal hash: `{report.goal_hash}`",
        f"- Iterations: `{report.iterations}`",
        f"- Checkpoints: `{report.checkpoints}`",
        f"- Duration: `{_format_duration(report.duration)}`",
        f"- Completion manifest ref: `{report.completion_manifest_ref or 'none'}`",
        "",
        "## Budget",
        "",
        "```json",
        json.dumps(report.budget, indent=2, sort_keys=True),
        "```",
        "",
        "## Final Evaluation",
        "",
        "```json",
        json.dumps(report.final_evaluation, indent=2, sort_keys=True),
        "```",
        "",
        "## Events",
        "",
        f"- Total events: `{len(events)}`",
        f"- Total evaluation snapshots: `{len(evaluations)}`",
    ]
    return "\n".join(lines)


def generate_json_report(
    run: RunModel,
    events: list[EventModel],
    evaluations: list[EvaluationModel],
    manifest: CompletionManifest | None,
) -> str:
    """Render a machine-readable JSON run report."""
    report = RunReport.from_parts(
        run,
        events,
        evaluations,
        manifest,
        completion_manifest_ref=_completion_manifest_ref(events, manifest),
    )
    return json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True)


def _budget_from_events(events: list[EventModel]) -> dict[str, Any]:
    model_calls = sum(1 for event in events if event.event_type == "MODEL_CALL")
    iterations = max((event.iteration for event in events), default=0)
    return BudgetUsage(
        iterations_consumed=iterations,
        model_calls=model_calls,
    ).model_dump(mode="json")


def _completion_manifest_ref(
    events: list[EventModel],
    manifest: CompletionManifest | None,
) -> str | None:
    if manifest is None:
        return None
    for event in reversed(events):
        artifact_hash = event.payload.get("artifact_hash")
        if isinstance(artifact_hash, str) and event.event_type == "ARTIFACT_STORED":
            return artifact_hash
    return None


def _duration_seconds(started_at: datetime, finished_at: datetime) -> float:
    return max(0.0, (finished_at - started_at).total_seconds())


def _format_duration(duration: float | None) -> str:
    if duration is None:
        return "unknown"
    return f"{duration:.2f}s"
