"""Evidence and artifact reference domain models."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ArtifactRef(BaseModel):
    """Reference to an artifact captured in append-only evidence."""

    model_config = ConfigDict(extra="forbid")

    path: str = Field(min_length=1)
    hash: str = Field(min_length=1)
    size_bytes: int = Field(ge=0)
    description: str | None = None


class Evidence(BaseModel):
    """Recorded evidence event for a run iteration."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    run_id: UUID
    iteration: int = Field(ge=0)
    candidate_id: UUID | None = None
    event_type: str = Field(min_length=1)
    payload: dict[str, Any] = Field(default_factory=dict)
    artifact_refs: list[ArtifactRef] = Field(default_factory=list)
    timestamp: datetime
