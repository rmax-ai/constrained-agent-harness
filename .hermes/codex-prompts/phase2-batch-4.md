# Phase 2 — Batch 4: Sandbox, Agent, and Evaluator Pipeline

## Task

Implement the sandbox interfaces, scripted agent, and evaluator pipeline foundation.

## Files to Create

### 1. `src/constrained_agent/sandbox/protocol.py`

- `ExecutionRequest` — Pydantic BaseModel: argv (list[str]), purpose (str), timeout_seconds (int = 60), env (dict[str, str] | None), working_dir (str | None)
- `ExecutionResult` — Pydantic BaseModel: stdout (str), stderr (str), exit_code (int), duration_seconds (float), timed_out (bool = False), truncated (bool = False), container_image (str | None)
- `Sandbox` — Protocol:
  - `async execute(self, request: ExecutionRequest) -> ExecutionResult`
  - `async close(self)` -> None

### 2. `src/constrained_agent/sandbox/fake.py`

- `FakeSandbox` — implements Sandbox for unit tests
  - Pre-registered command results: dict mapping "argv_string" -> ExecutionResult
  - `register(script: list[str], result: ExecutionResult)` — register expected output
  - Falls back to actual subprocess execution for unregistered commands (configurable)

### 3. `src/constrained_agent/agents/protocol.py`

- `FileEdit` — Pydantic BaseModel: path (str), operation (Literal["create", "replace", "patch", "delete"]), content (str | None), unified_diff (str | None)
- `CommandRequest` — Pydantic BaseModel: argv (list[str]), purpose (str), timeout_seconds (int = 60)
- `AgentProposal` — Pydantic BaseModel: summary (str), hypothesis (str), evidence_considered (list[str]), files_to_inspect (list[str]), edits (list[FileEdit]), commands (list[CommandRequest]), expected_effect (str), risk_notes (list[str]), completion_claimed (bool = False)
- `AgentContext` — Pydantic BaseModel: goal_summary (str), repository_map (str), candidate_diff (str), evaluation_failures (str), prior_rejected (str), remaining_budget (str), permitted_actions (list[str]), protected_summary (str), iteration (int)
- `CodingAgent` — Protocol:
  - `async propose_action(self, context: AgentContext) -> AgentProposal`
  - `get_model_info(self) -> dict` — returns model identifier, provider, params

### 4. `src/constrained_agent/agents/scripted.py`

- `ScriptedAgent` — implements CodingAgent with a deterministic script
  - Takes a list of pre-defined proposals (for testing)
  - Can simulate: success, failure, policy violations, false completion, regression
  - Useful for testing the controller without a live model

### 5. `src/constrained_agent/agents/replay.py`

- `ReplayAgent` — implements CodingAgent by replaying recorded proposals
  - Loads proposals from JSONL files
  - Useful for reproducing past runs

### 6. `src/constrained_agent/evaluators/protocol.py`

- `EvaluationContext` — Pydantic BaseModel: workspace (Path), repository_state (RepositoryState | None), sandbox (Sandbox | None), goal (GoalContract)
- `Evaluator` — Protocol:
  - `id: str`
  - `tier: EvaluationTier`
  - `async evaluate(self, context: EvaluationContext) -> EvaluationResult`

### 7. `src/constrained_agent/evaluators/command.py`

- `CommandEvaluator` — runs a generic command and captures exit code
  - Uses sandbox.execute()
  - Can be configured per-command from goal.yaml required_checks

### 8. `src/constrained_agent/evaluators/diff_size.py`

- `DiffSizeEvaluator` — checks diff size against limits
  - Measures lines added/removed

### 9. `src/constrained_agent/evaluators/pipeline.py`

- `EvaluatorPipeline` — orchestrates evaluator execution
  - `register(evaluator: Evaluator)` — add an evaluator
  - `async evaluate(self, context: EvaluationContext) -> EvaluationVector` — runs evaluators in tier order
  - Implements short-circuiting: if TIER_0 fails, skip remaining
  - Hard gates: policy violations, protected file changes, critical security
  - Returns combined EvaluationVector

## Tests

Create `tests/unit/test_agents.py` — scripted agent, proposal validation
Create `tests/unit/test_sandbox.py` — fake sandbox, execution results
Create `tests/unit/test_evaluators.py` — pipeline ordering, evaluation vector
