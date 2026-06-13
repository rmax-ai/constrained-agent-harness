# Phase 3 — Batch 2: Payment Webhook Benchmark

## Task

Create the complete payment webhook benchmark — the test target repository, visible tests, hidden tests, and reference solution.

## Files to Create

### 1. `benchmarks/payment_webhook/benchmark_manifest.yaml`

```yaml
name: payment-webhook
title: Payment Webhook Idempotency
description: >
  Fix duplicate payment creation from duplicate webhook deliveries.
language: python
framework: fastapi
default_goal: goal.yaml
```  

### 2. `benchmarks/payment_webhook/source_repo/` — a complete FastAPI project

Files:
- `pyproject.toml` — minimal deps: fastapi, uvicorn, pydantic, sqlalchemy, aiosqlite
- `README.md` — brief description
- `src/app.py` — FastAPI webhook endpoint with the intentional bug:
  - POST /webhook receives payment events
  - Each event has an `event_id` string
  - The endpoint creates a payment record in SQLite
  - **BUG**: No idempotency check — duplicate event_ids can create multiple payment rows
- `src/database.py` — SQLite setup, Payment model with columns: id (int, pk), event_id (str), amount (float), currency (str), created_at (datetime)
- `src/models.py` — Pydantic models for request/response
- `src/main.py` — uvicorn entry point
- `.gitignore`

### 3. `benchmarks/payment_webhook/goal.yaml`

A complete goal contract for the payment webhook benchmark:
```yaml
schema_version: "1.0"
task:
  id: payment-webhook-idempotency
  title: Prevent duplicate payment creation
  description: >
    Modify the target repository so that duplicate webhook deliveries
    do not create duplicate payment records.
acceptance:
  required_checks:
    - id: unit-tests
      evaluator: pytest
      command: ["pytest", "-q"]
      expected_exit_code: 0
      blocking: true
    - id: type-check
      evaluator: mypy
      command: ["mypy", "src"]
      expected_exit_code: 0
      blocking: true
  hidden_checks:
    directory: ../protected_tests
    writable: false
    reveal_failures_to_agent: summary_only
constraints:
  max_iterations: 20
  max_runtime_seconds: 3600
  writable_paths: ["src/"]
  protected_paths: ["tests/", "pyproject.toml"]
  allowed_commands: ["pytest", "mypy", "python", "git", "cat", "grep", "find"]
  forbidden_patterns: ["rm -rf", "curl", "wget"]
  network:
    mode: disabled
  dependencies:
    allow_changes: false
termination:
  success:
    require_all_blocking_checks: true
    require_hidden_checks: true
  failure:
    - iteration_limit_reached
    - runtime_budget_exhausted
```

### 4. `benchmarks/payment_webhook/source_repo/tests/test_webhook.py` — Visible Tests

Tests that the agent can see:
- `test_valid_webhook_creates_payment` — sends valid webhook, checks 200 + payment created
- `test_malformed_payload_rejected` — sends invalid JSON, checks 422
- `test_duplicate_sequential_delivery` — sends same event_id twice sequentially, expects second to be idempotent (currently FAILS because of the bug)
- `test_webhook_returns_payment_data` — checks response body

### 5. `benchmarks/payment_webhook/protected_tests/` — Hidden Tests (read-only)

The agent cannot see or modify these. They test:
- `test_concurrent_duplicate_delivery` — two concurrent requests with same event_id
- `test_transaction_rollback` — partial failure doesn't leave orphaned state
- `test_idempotency_key_persistence` — restart app, send duplicate, still idempotent
- `test_unexpected_event_types` — unknown event types handled gracefully
- `test_no_hardcoded_fixtures` — verify solution doesn't use hardcoded event_ids

### 6. `benchmarks/payment_webhook/reference_solution/` — Correct Implementation

- A manually verified correct solution stored outside the workspace
- Same files as source_repo but with idempotency fixed (database-backed dedup)
- Used ONLY for benchmark validation, never given to the agent

## Tests

Create `tests/unit/test_benchmark.py`:
- `test_benchmark_visible_tests_fail_initially` — visible tests should fail before fix
- `test_hidden_tests_not_writable` — protected tests directory is read-only
- `test_benchmark_validates_correctly` — benchmark_manifest.yaml is valid

## Files to Modify

- `pyproject.toml` — add benchmark as data files if needed
