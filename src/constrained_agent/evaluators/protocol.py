"""Evaluator protocol contracts."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, ConfigDict

from constrained_agent.domain.contracts import GoalContract
from constrained_agent.domain.evaluations import EvaluationResult, EvaluationTier
from constrained_agent.repository.protocol import RepositoryState
from constrained_agent.sandbox.protocol import Sandbox


class EvaluationContext(BaseModel):
    """Runtime context made available to each evaluator."""

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")

    workspace: Path
    repository_state: RepositoryState | None
    sandbox: Sandbox | None
    goal: GoalContract


class Evaluator(Protocol):
    """Protocol implemented by all evaluator plugins."""

    id: str
    tier: EvaluationTier

    async def evaluate(self, context: EvaluationContext) -> EvaluationResult:
        """Produce a detailed evaluation result for the current context."""
