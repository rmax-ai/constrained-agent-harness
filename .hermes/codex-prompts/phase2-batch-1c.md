# Phase 2 — Batch 1c: Approvals, Events, and State Machine

## Task

Create approval models, event types, and the state machine.

## Files to Create

### 1. `src/constrained_agent/domain/approvals.py`

- `ApprovalGate` — StrEnum: DEPENDENCY_CHANGE, PUBLIC_API_CHANGE, DATABASE_SCHEMA_CHANGE, SENSITIVE_FILE_CHANGE
- `ApprovalStatus` — StrEnum: PENDING, APPROVED, REJECTED, EXPIRED
- `Approval` — Pydantic BaseModel: id (UUID), run_id (UUID), gate (ApprovalGate), description (str), details (dict), status (ApprovalStatus), created_at (datetime), decided_at (datetime | None), decided_by (str | None)

### 2. `src/constrained_agent/domain/events.py`

- `EventType` — StrEnum: RUN_CREATED, STATE_TRANSITION, MODEL_CALL, PROPOSAL_RECEIVED, POLICY_CHECK, EXECUTION_STARTED, EXECUTION_COMPLETED, CHECKPOINT_CREATED, EVALUATION_COMPLETED, TRANSITION_DECIDED, APPROVAL_REQUESTED, APPROVAL_DECIDED, COMPLETION_DECLARED, RUN_FAILED, RUN_CANCELLED, ARTIFACT_STORED

- `Event` — Pydantic BaseModel: id (UUID), run_id (UUID), event_type (EventType), iteration (int), source_state (str | None), target_state (str | None), payload (dict), previous_event_hash (str | None), event_hash (str), timestamp (datetime)

Add a method `compute_hash(event: Event, previous_hash: str | None) -> str` that computes SHA-256 of canonical JSON representation.

- `TransitionEvent` — subclass of Event with typed transition fields: transition_id (UUID), from_state (str), to_state (str), decision (TransitionDecision), reason (str), candidate_id (UUID | None)

Use `from constrained_agent.controller.state_machine import TransitionDecision` — but that doesn't exist yet. Instead, define a `TransitionDecision` StrEnum directly: ACCEPT, REJECT, ROLLBACK, RETRY, BRANCH, REQUEST_APPROVAL, COMPLETE, FAIL.

### 3. `src/constrained_agent/controller/state_machine.py`

The explicit state machine for the controller.

- `ControllerState` — StrEnum with all states: CREATED, INITIALIZING, BASELINE_EVALUATION, BUILDING_CONTEXT, AWAITING_PROPOSAL, POLICY_CHECK, EXECUTING, CHECKPOINTING, EVALUATING, SELECTING_TRANSITION, AWAITING_APPROVAL, VERIFYING_COMPLETION, COMPLETED, FAILED, CANCELLED

- `TransitionDecision` — StrEnum: ACCEPT, REJECT, ROLLBACK, RETRY, BRANCH, REQUEST_APPROVAL, COMPLETE, FAIL

- `StateMachine` — class that:
  - Holds current state
  - Has a transition table (dict of valid_from_state -> list of valid target states)
  - `transition(target: ControllerState, decision: TransitionDecision)` -> validates transition is allowed, creates TransitionEvent, updates state
  - `permitted_transitions() -> list[ControllerState]` — returns valid next states
  - `validate(from_state, to_state, decision) -> bool` — returns whether transition is valid
  - Include PREVENT invalid transitions through code (not convention)
  - Generate unique event IDs for each transition

The transition table should capture the state machine logic from section 5.4 of the spec.

## Files to Modify

- `src/constrained_agent/domain/__init__.py` — add new exports
- `src/constrained_agent/controller/__init__.py` — add StateMachine, ControllerState, TransitionDecision

## Tests

Create `tests/unit/test_state_machine.py` with property tests using Hypothesis:
- Valid transitions don't raise
- Invalid transitions raise InvalidTransitionError
- Each state has at least one valid transition (except terminal states)
- Event chain is properly documented

Create `tests/unit/test_domain_models.py` with basic tests for each domain model:
- Contract validation
- Budget tracking
- Evaluation vector comparison
