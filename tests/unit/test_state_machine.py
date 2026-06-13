from __future__ import annotations

from uuid import uuid4

import pytest
from hypothesis import given
from hypothesis import strategies as st

from constrained_agent.controller import ControllerState, StateMachine, TransitionDecision
from constrained_agent.errors import InvalidTransitionError


MACHINE = StateMachine(run_id=uuid4())
VALID_TRANSITIONS = [
    (from_state, to_state, decision)
    for (from_state, to_state), decisions in MACHINE.decision_table.items()
    for decision in decisions
]
INVALID_TRANSITIONS = [
    (from_state, to_state, decision)
    for from_state in ControllerState
    for to_state in ControllerState
    for decision in TransitionDecision
    if (from_state, to_state, decision) not in VALID_TRANSITIONS
]
TERMINAL_STATES = {
    ControllerState.COMPLETED,
    ControllerState.FAILED,
    ControllerState.CANCELLED,
}


@given(st.sampled_from(VALID_TRANSITIONS))
def test_valid_transitions_do_not_raise(
    transition: tuple[ControllerState, ControllerState, TransitionDecision],
) -> None:
    from_state, to_state, decision = transition
    machine = StateMachine(run_id=uuid4(), initial_state=from_state)

    event = machine.transition(to_state, decision, iteration=1, reason="valid transition")

    assert machine.current_state is to_state
    assert event.from_state == from_state.value
    assert event.to_state == to_state.value
    assert event.decision.value == decision.value


@given(st.sampled_from(INVALID_TRANSITIONS))
def test_invalid_transitions_raise_invalid_transition_error(
    transition: tuple[ControllerState, ControllerState, TransitionDecision],
) -> None:
    from_state, to_state, decision = transition
    machine = StateMachine(run_id=uuid4(), initial_state=from_state)

    with pytest.raises(InvalidTransitionError):
        machine.transition(to_state, decision, iteration=1, reason="invalid transition")


def test_each_non_terminal_state_has_at_least_one_valid_transition() -> None:
    machine = StateMachine(run_id=uuid4())

    for state, targets in machine.transition_table.items():
        if state in TERMINAL_STATES:
            assert targets == ()
            continue
        assert targets


def test_event_chain_is_hash_linked_and_documented() -> None:
    machine = StateMachine(run_id=uuid4())

    first = machine.transition(
        ControllerState.INITIALIZING,
        TransitionDecision.ACCEPT,
        iteration=0,
        reason="run created",
    )
    second = machine.transition(
        ControllerState.BASELINE_EVALUATION,
        TransitionDecision.ACCEPT,
        iteration=0,
        reason="initialization complete",
    )

    assert first.previous_event_hash is None
    assert second.previous_event_hash == first.event_hash
    assert first.payload["reason"] == "run created"
    assert second.payload["reason"] == "initialization complete"
    assert first.event_hash == first.compute_hash(first, None)
    assert second.event_hash == second.compute_hash(second, first.event_hash)
