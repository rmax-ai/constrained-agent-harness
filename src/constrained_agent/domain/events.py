"""Event domain models with canonical hash-chain support."""

from __future__ import annotations

import json
from datetime import datetime
from enum import StrEnum
from hashlib import sha256
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TransitionDecision(StrEnum):
    """Controller decision applied to a transition edge."""

    ACCEPT = "ACCEPT"
    REJECT = "REJECT"
    ROLLBACK = "ROLLBACK"
    RETRY = "RETRY"
    BRANCH = "BRANCH"
    REQUEST_APPROVAL = "REQUEST_APPROVAL"
    COMPLETE = "COMPLETE"
    FAIL = "FAIL"


class EventType(StrEnum):
    """Persisted event classes emitted during controller execution."""

    RUN_CREATED = "RUN_CREATED"
    STATE_TRANSITION = "STATE_TRANSITION"
    MODEL_CALL = "MODEL_CALL"
    PROPOSAL_RECEIVED = "PROPOSAL_RECEIVED"
    POLICY_CHECK = "POLICY_CHECK"
    EXECUTION_STARTED = "EXECUTION_STARTED"
    EXECUTION_COMPLETED = "EXECUTION_COMPLETED"
    CHECKPOINT_CREATED = "CHECKPOINT_CREATED"
    EVALUATION_COMPLETED = "EVALUATION_COMPLETED"
    TRANSITION_DECIDED = "TRANSITION_DECIDED"
    APPROVAL_REQUESTED = "APPROVAL_REQUESTED"
    APPROVAL_DECIDED = "APPROVAL_DECIDED"
    COMPLETION_DECLARED = "COMPLETION_DECLARED"
    RUN_FAILED = "RUN_FAILED"
    RUN_CANCELLED = "RUN_CANCELLED"
    ARTIFACT_STORED = "ARTIFACT_STORED"


class Event(BaseModel):
    """Base persisted event in the append-only run history."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    run_id: UUID
    event_type: EventType
    iteration: int = Field(ge=0)
    source_state: str | None = None
    target_state: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    previous_event_hash: str | None = None
    event_hash: str = Field(min_length=1)
    timestamp: datetime

    @staticmethod
    def compute_hash(event: Event, previous_hash: str | None) -> str:
        """Compute the canonical SHA-256 hash for an event chain entry."""
        content = event.model_dump(
            mode="json",
            exclude={"event_hash", "previous_event_hash"},
        )
        content["previous_event_hash"] = previous_hash
        canonical_json = json.dumps(
            content,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )
        return sha256(canonical_json.encode("utf-8")).hexdigest()


class TransitionEvent(Event):
    """Typed event for an explicit controller state transition."""

    transition_id: UUID
    from_state: str = Field(min_length=1)
    to_state: str = Field(min_length=1)
    decision: TransitionDecision
    reason: str = Field(min_length=1)
    candidate_id: UUID | None = None
