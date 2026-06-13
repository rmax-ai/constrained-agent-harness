# Domain Model

The domain model is the heart of the system — typed contracts with no
infrastructure dependencies, validated at every boundary by Pydantic v2.

## Core Types

### GoalContract

The input specification for a run. Defines the task, acceptance criteria,
constraints, termination conditions, and experiment configuration.

```python
class GoalContract(BaseModel):
    schema_version: str
    task: TaskDescription
    model: ModelConfig
    acceptance: AcceptanceCriteria
    constraints: ConstraintSet
    approval_gates: list[ApprovalGate]
    termination: TerminationConditions
    experiment: ExperimentConfig
```

### Run

A single execution of the harness against a goal. Contains the run ID,
status, goal hash, initial commit reference, and timestamps.

### Candidate

A snapshot of the repository state at a given iteration. Each candidate
has a parent (for traceability), depth, status, and iteration number.

### AgentProposal

The output of an agent invocation. Contains:

- **summary**: Human-readable description of the proposed change
- **hypothesis**: What the agent expects to happen
- **edits**: File edit operations (replace, insert, delete)
- **commands**: Shell commands to run in the sandbox
- **completion_claimed**: Whether the agent believes the task is done
- **write_files**: Paths the agent expects to modify

## Evaluation

### EvaluationVector

A typed, structured evaluation result with named fields for passing/failing
tests, runtime metrics, and policy violations.

### EvaluationTier

Evaluation priority levels that determine execution order and
short-circuit behavior:

| Tier | Name | Example |
|------|------|---------|
| 1 | FAST_STATIC_CHECKS | Diff size, file count |
| 2 | TARGETED_TESTS | Visible benchmark tests |
| 3 | FULL_VERIFICATION | Hidden tests, full suite |

## Budget & Constraints

### BudgetTracker

Enforces resource limits defined in the goal contract:

- **max_iterations**: Maximum controller loop iterations
- **max_runtime_seconds**: Total wall-clock time
- **max_model_calls**: Maximum model invocations

### ConstraintSet

Defines the operational boundaries for a run:

- **writable_paths**: Glob patterns for editable files
- **protected_paths**: Read-only paths (tests, config)
- **allowed_commands**: Permitted command prefixes
- **forbidden_patterns**: Prohibited command patterns
- **network_mode**: on/off
- **dependency_policy**: frozen or open

## Events

All state changes are recorded as typed, hash-chained events:

| Event Type | Meaning |
|------------|---------|
| RUN_STARTED | Run initialized |
| MODEL_CALL | Model invoked |
| PROPOSAL_RECEIVED | Proposal submitted |
| POLICY_CHECK | Policy validation result |
| CANDIDATE_CREATED | New candidate state stored |
| EVALUATION_COMPLETED | Evaluation finished |
| TRANSITION_DECIDED | Controller decided next step |
| ARTIFACT_STORED | Artifact persisted |
| COMPLETION_DECLARED | Agent claimed completion |
| CHECKPOINT_CREATED | Repository checkpoint |
| RUN_FINISHED | Run completed or failed |

## State Machine

The state machine model has the following states:

```
INIT → RUNNING → COMPLETED
                → FAILED
                → CANCELLED
                → PAUSED → RUNNING
```

Transitions are validated against a transition table — invalid transitions
raise `InvalidTransitionError`.

## Completion Manifest

The final artifact of a successful run, containing:

- Model provider and identifier
- Final evaluation vector
- Budget usage (iterations consumed, model calls)
- Artifact hashes for integrity verification
