# Phase 3 — Batch 3: Reports, CLI, Benchmark Validation, End-to-End Tests

## Task

Implement reporting, CLI inspect commands, benchmark validation, and end-to-end tests.

## Files to Create

### 1. `src/constrained_agent/reporting/run_report.py`

- `RunReport` — Pydantic BaseModel for run report data:
  - run_id, status, model, goal_hash, iterations, checkpoints, final_evaluation, budget, duration, completion_manifest_ref
- `generate_markdown_report(run, events, evaluations, manifest) -> str` — human-readable report
- `generate_json_report(run, events, evaluations, manifest) -> str` — machine-readable JSON

### 2. `src/constrained_agent/reporting/experiment_report.py`

- `ExperimentReport` — aggregate report across multiple runs:
  - mode, repetitions, declared_completion_rate, verified_completion_rate, verified_completion_precision, hidden_test_success_rate, false_completion_count, policy_violation_count, rollback_count, model_calls, token_usage, estimated_cost, wall_clock_duration
- `verified_completion_precision = runs_declared_complete_and_verified / all_runs_declared_complete`
- Handle zero denominator explicitly
- Generate JSON + Markdown + terminal summary

### 3. `src/constrained_agent/reporting/metrics.py`

- Metrics calculation functions
- `compute_run_metrics(run, candidates, events) -> dict` — per-run metrics
- `compute_experiment_metrics(runs) -> ExperimentReport` — cross-run aggregation

### 4. CLI Commands — update `src/constrained_agent/cli/app.py`

Add these commands (or create separate module files):

- `cah inspect run <run-id>` — show run details
- `cah inspect events <run-id>` — list events
- `cah inspect budget <run-id>` — show budget usage
- `cah inspect candidate <candidate-id>` — show candidate details
- `cah report run <run-id>` — generate run report
- `cah artifacts verify <run-id>` — verify artifact hash chain
- `cah db upgrade` — run Alembic migrations
- `cah benchmark validate <name>` — validate benchmark integrity
- `cah experiment run` — run experiment with repetitions

Create these as separate module files in `src/constrained_agent/cli/`:
- `doctor.py` (move existing doctor code)
- `inspect.py`
- `report.py`
- `experiment.py`
- `benchmark.py`

### 5. `scripts/validate_benchmark.py`

- Validates benchmark structure and integrity
- Checks all required files exist
- Runs visible tests to confirm initial failure
- Checks protected tests are read-only
- Verifies reference solution exists
- Usage: `uv run python scripts/validate_benchmark.py benchmarks/payment_webhook`

### 6. `scripts/run_smoke_test.py`

- End-to-end smoke test:
  1. Creates a temporary workspace
  2. Copies benchmark source repo
  3. Runs scripted agent against it
  4. Verifies completion manifest is produced
  5. Verifies budget accounting
  6. Cleans up

### 7. End-to-End Tests

Create `tests/end_to_end/test_scripted_run.py`:
- Scripted agent successfully fixes benchmark
- Policy enforcement: agent attempts protected edit → rejected
- False completion: scripted agent claims completion, hidden tests fail → refused
- Budget exhaustion terminates cleanly

Create `tests/end_to_end/test_policy_enforcement.py`:
- Protected file modifications are rejected
- Forbidden commands are blocked
- Path traversal attempts fail

## Files to Modify

- `src/constrained_agent/cli/app.py` — add new commands, refactor
- `src/constrained_agent/cli/__init__.py` — update imports
- `pyproject.toml` — add entry points if needed
