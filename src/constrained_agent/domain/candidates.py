"""Candidate repository state domain models."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from constrained_agent.domain.evaluations import EvaluationVector
else:
    EvaluationVector = Any

CandidateId = UUID


class CandidateStatus(StrEnum):
    """Lifecycle states for a candidate repository state."""

    ACTIVE = "ACTIVE"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    ROLLED_BACK = "ROLLED_BACK"
    OUTDATED = "OUTDATED"


class Candidate(BaseModel):
    """A candidate repository state proposed during a run."""

    model_config = ConfigDict(extra="forbid")

    id: CandidateId
    repository_state_hash: str = Field(min_length=1)
    evaluation: EvaluationVector | None = None
    parent_id: CandidateId | None = None
    depth: int = Field(ge=0)
    status: CandidateStatus
    iteration: int = Field(ge=0)
    created_at: datetime
