# Phase 3 — Batch 1: Docker Sandbox, Controller, Completion Manifest

## Task

Implement the Docker sandbox, the full controller assembly, and the completion manifest.

## Files to Create

### 1. `src/constrained_agent/sandbox/docker.py`

- `DockerSandbox` — implements Sandbox Protocol using the `docker` Python SDK
  - `__init__` takes: image (str), cpu_limit (float), memory_limit (str), network_disabled (bool), read_only (bool), workspace_mount (str), protected_mounts (list[str]), user (str = "nobody"), env_allowlist (list[str])
  - `async execute(request: ExecutionRequest) -> ExecutionResult` — runs command in Docker container with:
    - Resource limits (CPU, memory, pids_limit)
    - No host network by default
    - Read-only base filesystem
    - Writable workspace mount
    - Protected tests mounted read-only
    - No Docker socket
    - No privileged mode
    - Non-root container user
    - Execution timeout
    - Output-size limit (1MB cap)
    - Environment-variable allowlist
  - `async close()` — cleanup containers
  - Container gets removed after each execution
  - Returns: stdout, stderr, exit_code, duration, timeout flag, truncation flag, container image digest

### 2. `src/constrained_agent/controller/controller.py`

- `Controller` — orchestrates the full run lifecycle:
  - `__init__` takes: goal contract, sandbox, repository store, evaluator pipeline, agent, artifact store, event store, budget tracker
  - `async run()` — main loop:
    1. CREATED → INITIALIZING: create run record, validate goal
    2. INITIALIZING → BASELINE_EVALUATION: evaluate initial repo state
    3. BASELINE_EVALUATION → BUILDING_CONTEXT: prepare context
    4. BUILDING_CONTEXT → AWAITING_PROPOSAL: build agent context
    5. AWAITING_PROPOSAL → POLICY_CHECK: invoke agent, validate proposal
    6. POLICY_CHECK → EXECUTING: apply edits, run commands in sandbox
    7. EXECUTING → CHECKPOINTING: git checkpoint
    8. CHECKPOINTING → EVALUATING: run evaluator pipeline
    9. EVALUATING → SELECTING_TRANSITION: decide what to do
    10. SELECTING_TRANSITION → ACCEPT/REJECT/ROLLBACK/RETRY/BRANCH/etc.
    11. If COMPLETE → VERIFYING_COMPLETION → COMPLETED
    - Every transition is persisted as an Event
    - Every iteration checks budget
    - Stagnation detection triggers checkpoint restore
    
- `TransitionPolicy` in `transition_policy.py`:
  - `decide(self, vector: EvaluationVector, contract: GoalContract, history: list[Candidate]) -> TransitionDecision`
  - Uses evaluation vector + history to decide the next transition
  - For scripted runs: use deterministic decision logic

### 3. `src/constrained_agent/artifacts/manifest.py`

- `CompletionManifest` — Pydantic BaseModel with all manifest fields:
  - run_id, goal_contract_hash, initial_repository_commit, final_repository_commit, model_provider, model_identifier, adk_version, python_version, container_image, evaluator_versions, final_evaluation_vector, hidden_check_result, budget_usage, event_chain_head_hash, artifact_hashes (list), completion_timestamp
- `generate_manifest(run, final_candidate, artifact_store, event_store) -> CompletionManifest`
- `verify_manifest(manifest, artifact_store) -> bool` — verify hash chain

## Tests

Create `tests/integration/test_controller.py`:
- Controller orchestrates a full run lifecycle
- Transition decisions are made and persisted
- Budget exhaustion terminates cleanly
- Completion manifest is produced and verifiable

## Files to Modify

- `src/constrained_agent/controller/__init__.py` — add Controller, TransitionPolicy exports
- `src/constrained_agent/artifacts/__init__.py` — add manifest exports
