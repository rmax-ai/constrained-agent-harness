"""Experiment-level aggregate reporting."""

from __future__ import annotations

import json

from pydantic import BaseModel, ConfigDict, Field


class ExperimentReport(BaseModel):
    """Aggregate metrics for a batch of runs."""

    model_config = ConfigDict(extra="forbid")

    mode: str = Field(min_length=1)
    repetitions: int = Field(ge=0)
    declared_completion_rate: float = Field(ge=0.0, le=1.0)
    verified_completion_rate: float = Field(ge=0.0, le=1.0)
    verified_completion_precision: float = Field(ge=0.0, le=1.0)
    hidden_test_success_rate: float = Field(ge=0.0, le=1.0)
    false_completion_count: int = Field(ge=0)
    policy_violation_count: int = Field(ge=0)
    rollback_count: int = Field(ge=0)
    model_calls: int = Field(ge=0)
    token_usage: int = Field(ge=0)
    estimated_cost: float = Field(ge=0.0)
    wall_clock_duration: float = Field(ge=0.0)

    def to_json(self) -> str:
        """Serialize the aggregate report as JSON."""
        return json.dumps(self.model_dump(mode="json"), indent=2, sort_keys=True)

    def to_markdown(self) -> str:
        """Serialize the aggregate report as markdown."""
        lines = [
            "# Experiment Report",
            "",
            f"- Mode: `{self.mode}`",
            f"- Repetitions: `{self.repetitions}`",
            f"- Declared completion rate: `{self.declared_completion_rate:.3f}`",
            f"- Verified completion rate: `{self.verified_completion_rate:.3f}`",
            f"- Verified completion precision: `{self.verified_completion_precision:.3f}`",
            f"- Hidden test success rate: `{self.hidden_test_success_rate:.3f}`",
            f"- False completion count: `{self.false_completion_count}`",
            f"- Policy violation count: `{self.policy_violation_count}`",
            f"- Rollback count: `{self.rollback_count}`",
            f"- Model calls: `{self.model_calls}`",
            f"- Token usage: `{self.token_usage}`",
            f"- Estimated cost: `${self.estimated_cost:.4f}`",
            f"- Wall clock duration: `{self.wall_clock_duration:.2f}s`",
        ]
        return "\n".join(lines)

    def to_terminal_summary(self) -> str:
        """Render a concise terminal summary."""
        return (
            f"mode={self.mode} repetitions={self.repetitions} "
            f"verified={self.verified_completion_rate:.3f} "
            f"precision={self.verified_completion_precision:.3f} "
            f"hidden={self.hidden_test_success_rate:.3f} "
            f"policy_violations={self.policy_violation_count} "
            f"rollbacks={self.rollback_count}"
        )
