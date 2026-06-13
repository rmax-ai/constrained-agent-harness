"""Run identity and lifecycle domain models."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

RunId = UUID


class RunStatus(StrEnum):
    """Lifecycle states for a run."""

    CREATED = "CREATED"
    INITIALIZING = "INITIALIZING"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class Run(BaseModel):
    """Top-level record for an execution run."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    status: RunStatus
    goal_hash: str = Field(min_length=1)
    initial_commit: str = Field(min_length=1)
    experiment_mode: str = Field(min_length=1)
    created_at: datetime
    updated_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)
