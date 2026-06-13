"""Approval domain models for human-gated controller actions."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ApprovalGate(StrEnum):
    """Types of changes that require explicit human approval."""

    DEPENDENCY_CHANGE = "DEPENDENCY_CHANGE"
    PUBLIC_API_CHANGE = "PUBLIC_API_CHANGE"
    DATABASE_SCHEMA_CHANGE = "DATABASE_SCHEMA_CHANGE"
    SENSITIVE_FILE_CHANGE = "SENSITIVE_FILE_CHANGE"


class ApprovalStatus(StrEnum):
    """Lifecycle state of an approval request."""

    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class Approval(BaseModel):
    """Human approval record for a gated controller transition."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    run_id: UUID
    gate: ApprovalGate
    description: str = Field(min_length=1)
    details: dict[str, Any] = Field(default_factory=dict)
    status: ApprovalStatus
    created_at: datetime
    decided_at: datetime | None = None
    decided_by: str | None = None
