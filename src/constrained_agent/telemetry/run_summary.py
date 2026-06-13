"""Aggregate run summary built from persisted event data."""

from __future__ import annotations

from collections import Counter
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from constrained_agent.persistence.models import EventModel


class RunSummary(BaseModel):
    """Aggregate summary of a completed or in-flight run.

    Built from the event store — no mutable runtime state dependency.
    """

    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(min_length=1)
    duration_seconds: float = Field(ge=0.0)
    total_iterations: int = Field(ge=0)
    decisions: dict[str, int] = Field(default_factory=dict)
    evaluator_passes: int = Field(ge=0)
    evaluator_failures: int = Field(ge=0)
    final_approval_status: str | None = None
    artifact_count: int = Field(ge=0)
    total_token_estimate: int = Field(ge=0)
    model_calls: int = Field(ge=0)

    @classmethod
    def from_events(
        cls,
        run_id: str,
        events: list[EventModel],
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> RunSummary:
        """Build a summary by replaying the event chain."""
        decision_counter: Counter[str] = Counter()
        evaluator_passes = 0
        evaluator_failures = 0
        artifact_count = 0
        model_calls = 0
        total_tokens = 0
        final_approval: str | None = None
        max_iteration = 0

        for event in events:
            payload = event.payload or {}
            max_iteration = max(max_iteration, event.iteration)

            if event.event_type == "TRANSITION_DECIDED":
                decision = payload.get("decision", "UNKNOWN")
                decision_counter[decision] += 1
                if decision == "COMPLETE":
                    final_approval = "approved"

            elif event.event_type == "EVALUATION_COMPLETED":
                passed = payload.get("passed", False)
                if passed:
                    evaluator_passes += 1
                else:
                    evaluator_failures += 1

            elif event.event_type == "ARTIFACT_STORED":
                artifact_count += 1

            elif event.event_type == "MODEL_CALL":
                model_calls += 1
                total_tokens += payload.get("token_estimate", 0)

        duration = 0.0
        if start_time and end_time:
            duration = max(0.0, (end_time - start_time).total_seconds())
        elif events:
            first = events[0].timestamp
            last = events[-1].timestamp
            if isinstance(first, datetime) and isinstance(last, datetime):
                duration = max(0.0, (last - first).total_seconds())

        return cls(
            run_id=run_id,
            duration_seconds=duration,
            total_iterations=max_iteration,
            decisions=dict(decision_counter),
            evaluator_passes=evaluator_passes,
            evaluator_failures=evaluator_failures,
            final_approval_status=final_approval,
            artifact_count=artifact_count,
            total_token_estimate=total_tokens,
            model_calls=model_calls,
        )

    def to_terminal(self) -> str:
        """Render a concise terminal-friendly summary."""
        decisions_str = ", ".join(f"{k}:{v}" for k, v in sorted(self.decisions.items()))
        return (
            f"Run {self.run_id[:8]} | iterations={self.total_iterations} "
            f"duration={self.duration_seconds:.1f}s "
            f"approval={self.final_approval_status or 'running'} "
            f"decisions=[{decisions_str}] "
            f"eval=({self.evaluator_passes}P/{self.evaluator_failures}F) "
            f"artifacts={self.artifact_count} tokens={self.total_token_estimate}"
        )
