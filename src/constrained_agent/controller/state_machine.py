"""Explicit controller state machine and validated transitions."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from constrained_agent.domain.events import (
    EventType,
    TransitionEvent,
)
from constrained_agent.domain.events import (
    TransitionDecision as EventTransitionDecision,
)
from constrained_agent.errors import InvalidTransitionError


class ControllerState(StrEnum):
    """Controller runtime states."""

    CREATED = "CREATED"
    INITIALIZING = "INITIALIZING"
    BASELINE_EVALUATION = "BASELINE_EVALUATION"
    BUILDING_CONTEXT = "BUILDING_CONTEXT"
    AWAITING_PROPOSAL = "AWAITING_PROPOSAL"
    POLICY_CHECK = "POLICY_CHECK"
    EXECUTING = "EXECUTING"
    CHECKPOINTING = "CHECKPOINTING"
    EVALUATING = "EVALUATING"
    SELECTING_TRANSITION = "SELECTING_TRANSITION"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    VERIFYING_COMPLETION = "VERIFYING_COMPLETION"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class TransitionDecision(StrEnum):
    """Controller decision applied after each stage."""

    ACCEPT = "ACCEPT"
    REJECT = "REJECT"
    ROLLBACK = "ROLLBACK"
    RETRY = "RETRY"
    BRANCH = "BRANCH"
    REQUEST_APPROVAL = "REQUEST_APPROVAL"
    COMPLETE = "COMPLETE"
    FAIL = "FAIL"


_TRANSITION_TABLE: dict[ControllerState, tuple[ControllerState, ...]] = {
    ControllerState.CREATED: (
        ControllerState.INITIALIZING,
        ControllerState.CANCELLED,
        ControllerState.FAILED,
    ),
    ControllerState.INITIALIZING: (
        ControllerState.BASELINE_EVALUATION,
        ControllerState.CANCELLED,
        ControllerState.FAILED,
    ),
    ControllerState.BASELINE_EVALUATION: (
        ControllerState.BUILDING_CONTEXT,
        ControllerState.CANCELLED,
        ControllerState.FAILED,
    ),
    ControllerState.BUILDING_CONTEXT: (
        ControllerState.AWAITING_PROPOSAL,
        ControllerState.CANCELLED,
        ControllerState.FAILED,
    ),
    ControllerState.AWAITING_PROPOSAL: (
        ControllerState.POLICY_CHECK,
        ControllerState.CANCELLED,
        ControllerState.FAILED,
    ),
    ControllerState.POLICY_CHECK: (
        ControllerState.EXECUTING,
        ControllerState.AWAITING_APPROVAL,
        ControllerState.SELECTING_TRANSITION,
        ControllerState.CANCELLED,
        ControllerState.FAILED,
    ),
    ControllerState.EXECUTING: (
        ControllerState.CHECKPOINTING,
        ControllerState.SELECTING_TRANSITION,
        ControllerState.CANCELLED,
        ControllerState.FAILED,
    ),
    ControllerState.CHECKPOINTING: (
        ControllerState.EVALUATING,
        ControllerState.SELECTING_TRANSITION,
        ControllerState.CANCELLED,
        ControllerState.FAILED,
    ),
    ControllerState.EVALUATING: (
        ControllerState.SELECTING_TRANSITION,
        ControllerState.CANCELLED,
        ControllerState.FAILED,
    ),
    ControllerState.SELECTING_TRANSITION: (
        ControllerState.BUILDING_CONTEXT,
        ControllerState.AWAITING_APPROVAL,
        ControllerState.VERIFYING_COMPLETION,
        ControllerState.CANCELLED,
        ControllerState.FAILED,
    ),
    ControllerState.AWAITING_APPROVAL: (
        ControllerState.POLICY_CHECK,
        ControllerState.SELECTING_TRANSITION,
        ControllerState.CANCELLED,
        ControllerState.FAILED,
    ),
    ControllerState.VERIFYING_COMPLETION: (
        ControllerState.COMPLETED,
        ControllerState.BUILDING_CONTEXT,
        ControllerState.CANCELLED,
        ControllerState.FAILED,
    ),
    ControllerState.COMPLETED: (),
    ControllerState.FAILED: (),
    ControllerState.CANCELLED: (),
}


_DECISION_TABLE: dict[tuple[ControllerState, ControllerState], tuple[TransitionDecision, ...]] = {
    (ControllerState.CREATED, ControllerState.INITIALIZING): (TransitionDecision.ACCEPT,),
    (ControllerState.CREATED, ControllerState.CANCELLED): (TransitionDecision.FAIL,),
    (ControllerState.CREATED, ControllerState.FAILED): (TransitionDecision.FAIL,),
    (ControllerState.INITIALIZING, ControllerState.BASELINE_EVALUATION): (TransitionDecision.ACCEPT,),
    (ControllerState.INITIALIZING, ControllerState.CANCELLED): (TransitionDecision.FAIL,),
    (ControllerState.INITIALIZING, ControllerState.FAILED): (TransitionDecision.FAIL,),
    (ControllerState.BASELINE_EVALUATION, ControllerState.BUILDING_CONTEXT): (TransitionDecision.ACCEPT,),
    (ControllerState.BASELINE_EVALUATION, ControllerState.CANCELLED): (TransitionDecision.FAIL,),
    (ControllerState.BASELINE_EVALUATION, ControllerState.FAILED): (TransitionDecision.FAIL,),
    (ControllerState.BUILDING_CONTEXT, ControllerState.AWAITING_PROPOSAL): (TransitionDecision.ACCEPT,),
    (ControllerState.BUILDING_CONTEXT, ControllerState.CANCELLED): (TransitionDecision.FAIL,),
    (ControllerState.BUILDING_CONTEXT, ControllerState.FAILED): (TransitionDecision.FAIL,),
    (ControllerState.AWAITING_PROPOSAL, ControllerState.POLICY_CHECK): (TransitionDecision.ACCEPT,),
    (ControllerState.AWAITING_PROPOSAL, ControllerState.CANCELLED): (TransitionDecision.FAIL,),
    (ControllerState.AWAITING_PROPOSAL, ControllerState.FAILED): (TransitionDecision.FAIL,),
    (ControllerState.POLICY_CHECK, ControllerState.EXECUTING): (TransitionDecision.ACCEPT,),
    (ControllerState.POLICY_CHECK, ControllerState.AWAITING_APPROVAL): (
        TransitionDecision.REQUEST_APPROVAL,
    ),
    (ControllerState.POLICY_CHECK, ControllerState.SELECTING_TRANSITION): (
        TransitionDecision.REJECT,
        TransitionDecision.RETRY,
        TransitionDecision.ROLLBACK,
    ),
    (ControllerState.POLICY_CHECK, ControllerState.CANCELLED): (TransitionDecision.FAIL,),
    (ControllerState.POLICY_CHECK, ControllerState.FAILED): (TransitionDecision.FAIL,),
    (ControllerState.EXECUTING, ControllerState.CHECKPOINTING): (TransitionDecision.ACCEPT,),
    (ControllerState.EXECUTING, ControllerState.SELECTING_TRANSITION): (
        TransitionDecision.REJECT,
        TransitionDecision.RETRY,
        TransitionDecision.ROLLBACK,
    ),
    (ControllerState.EXECUTING, ControllerState.CANCELLED): (TransitionDecision.FAIL,),
    (ControllerState.EXECUTING, ControllerState.FAILED): (TransitionDecision.FAIL,),
    (ControllerState.CHECKPOINTING, ControllerState.EVALUATING): (TransitionDecision.ACCEPT,),
    (ControllerState.CHECKPOINTING, ControllerState.SELECTING_TRANSITION): (
        TransitionDecision.RETRY,
        TransitionDecision.ROLLBACK,
    ),
    (ControllerState.CHECKPOINTING, ControllerState.CANCELLED): (TransitionDecision.FAIL,),
    (ControllerState.CHECKPOINTING, ControllerState.FAILED): (TransitionDecision.FAIL,),
    (ControllerState.EVALUATING, ControllerState.SELECTING_TRANSITION): (TransitionDecision.ACCEPT,),
    (ControllerState.EVALUATING, ControllerState.CANCELLED): (TransitionDecision.FAIL,),
    (ControllerState.EVALUATING, ControllerState.FAILED): (TransitionDecision.FAIL,),
    (ControllerState.SELECTING_TRANSITION, ControllerState.BUILDING_CONTEXT): (
        TransitionDecision.ACCEPT,
        TransitionDecision.REJECT,
        TransitionDecision.RETRY,
        TransitionDecision.ROLLBACK,
        TransitionDecision.BRANCH,
    ),
    (ControllerState.SELECTING_TRANSITION, ControllerState.AWAITING_APPROVAL): (
        TransitionDecision.REQUEST_APPROVAL,
    ),
    (ControllerState.SELECTING_TRANSITION, ControllerState.VERIFYING_COMPLETION): (
        TransitionDecision.COMPLETE,
    ),
    (ControllerState.SELECTING_TRANSITION, ControllerState.CANCELLED): (TransitionDecision.FAIL,),
    (ControllerState.SELECTING_TRANSITION, ControllerState.FAILED): (TransitionDecision.FAIL,),
    (ControllerState.AWAITING_APPROVAL, ControllerState.POLICY_CHECK): (
        TransitionDecision.ACCEPT,
    ),
    (ControllerState.AWAITING_APPROVAL, ControllerState.SELECTING_TRANSITION): (
        TransitionDecision.REJECT,
        TransitionDecision.ROLLBACK,
    ),
    (ControllerState.AWAITING_APPROVAL, ControllerState.CANCELLED): (TransitionDecision.FAIL,),
    (ControllerState.AWAITING_APPROVAL, ControllerState.FAILED): (TransitionDecision.FAIL,),
    (ControllerState.VERIFYING_COMPLETION, ControllerState.COMPLETED): (
        TransitionDecision.COMPLETE,
    ),
    (ControllerState.VERIFYING_COMPLETION, ControllerState.BUILDING_CONTEXT): (
        TransitionDecision.RETRY,
        TransitionDecision.REJECT,
    ),
    (ControllerState.VERIFYING_COMPLETION, ControllerState.CANCELLED): (TransitionDecision.FAIL,),
    (ControllerState.VERIFYING_COMPLETION, ControllerState.FAILED): (TransitionDecision.FAIL,),
}


class StateMachine:
    """Validated controller state machine with transition event history."""

    def __init__(
        self,
        *,
        run_id: UUID,
        initial_state: ControllerState = ControllerState.CREATED,
    ) -> None:
        self._run_id = run_id
        self._state = initial_state
        self._events: list[TransitionEvent] = []

    @property
    def current_state(self) -> ControllerState:
        """Return the current controller state."""
        return self._state

    @property
    def events(self) -> list[TransitionEvent]:
        """Return the transition history."""
        return list(self._events)

    @property
    def transition_table(self) -> dict[ControllerState, tuple[ControllerState, ...]]:
        """Return the immutable transition table."""
        return dict(_TRANSITION_TABLE)

    @property
    def decision_table(
        self,
    ) -> dict[tuple[ControllerState, ControllerState], tuple[TransitionDecision, ...]]:
        """Return the valid decisions for each transition edge."""
        return dict(_DECISION_TABLE)

    def permitted_transitions(self) -> list[ControllerState]:
        """Return valid next states from the current state."""
        return list(_TRANSITION_TABLE[self._state])

    def validate(
        self,
        from_state: ControllerState,
        to_state: ControllerState,
        decision: TransitionDecision,
    ) -> bool:
        """Return whether the transition edge and decision are valid."""
        if to_state not in _TRANSITION_TABLE.get(from_state, ()):
            return False
        return decision in _DECISION_TABLE.get((from_state, to_state), ())

    def transition(
        self,
        target: ControllerState,
        decision: TransitionDecision,
        *,
        iteration: int = 0,
        reason: str = "state transition",
        candidate_id: UUID | None = None,
    ) -> TransitionEvent:
        """Advance to a new state after validating the requested edge."""
        if not self.validate(self._state, target, decision):
            raise InvalidTransitionError(
                f"invalid transition {self._state} -> {target} for decision {decision}"
            )

        previous_hash = self._events[-1].event_hash if self._events else None
        transition_id = uuid4()
        event = TransitionEvent(
            id=uuid4(),
            run_id=self._run_id,
            event_type=EventType.STATE_TRANSITION,
            iteration=iteration,
            source_state=self._state.value,
            target_state=target.value,
            payload={
                "transition_id": str(transition_id),
                "decision": decision.value,
                "reason": reason,
                "candidate_id": str(candidate_id) if candidate_id is not None else None,
            },
            previous_event_hash=previous_hash,
            event_hash="pending",
            timestamp=datetime.now(UTC),
            transition_id=transition_id,
            from_state=self._state.value,
            to_state=target.value,
            decision=EventTransitionDecision(decision.value),
            reason=reason,
            candidate_id=candidate_id,
        )
        event.event_hash = TransitionEvent.compute_hash(event, previous_hash)
        self._events.append(event)
        self._state = target
        return event
