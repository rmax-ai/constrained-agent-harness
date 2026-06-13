# Phase 2 — Batch 1a: Core Domain Models

## Task

Create the foundational domain models for constrained-agent-harness.

These are PURE domain models — NO infrastructure dependencies (no SQLAlchemy, no I/O). They define the typed contracts that the entire system uses.

## Files to Create

### 1. `src/constrained_agent/domain/contracts.py`

A typed YAML contract describing task bounds and configuration.

Key types:
- `GoalContract` — Pydantic BaseModel with schema_version, task (TaskDef), model (ModelConfig), acceptance (AcceptanceConfig), constraints (ConstraintConfig), approval_gates, termination conditions, experiment config
- `TaskDef` — id, title, description
- `ModelConfig` — provider, name, temperature
- `AcceptanceConfig` — required_checks (list of CheckDef), hidden_checks (HiddenCheckConfig)
- `CheckDef` — id, evaluator, command, expected_exit_code, blocking
- `HiddenCheckConfig` — directory, writable=False, reveal_failures_to_agent (NONE | SUMMARY_ONLY | FULL)
- `ConstraintConfig` — max_iterations, max_runtime_seconds, max_model_calls, writable_paths, protected_paths, allowed_commands, forbidden_patterns, network mode, dependency policy
- `TerminationConfig` — success conditions, failure conditions list
- `ExperimentConfig` — context_strategy, completion_strategy, checkpoint_strategy, branching_factor
- `ContractValidator` — classmethod validate(goal: GoalContract) -> list[str] returning actionable error messages
- `GoalContract.hash()` -> str — SHA-256 of canonical YAML serialization

Use Pydantic v2 with `model_config = ConfigDict(extra="forbid")`.

### 2. `src/constrained_agent/domain/runs.py`

- `RunId` — UUID-based NewType or simple str wrapper
- `RunStatus` — StrEnum: CREATED, INITIALIZING, ACTIVE, PAUSED, COMPLETED, FAILED, CANCELLED
- `Run` — Pydantic BaseModel: id (UUID), status (RunStatus), goal_hash (str), initial_commit (str), experiment_mode (str), created_at, updated_at, metadata (dict)

### 3. `src/constrained_agent/domain/candidates.py`

- `CandidateId` — UUID
- `CandidateStatus` — StrEnum: ACTIVE, ACCEPTED, REJECTED, ROLLED_BACK, OUTDATED
- `Candidate` — Pydantic BaseModel: id (CandidateId), repository_state_hash (str), evaluation (EvaluationVector | None), parent_id (CandidateId | None), depth (int), status (CandidateStatus), iteration (int), created_at

Keep them focused, small, and well-typed.
