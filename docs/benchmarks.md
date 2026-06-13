# Benchmarks

A benchmark is a self-contained problem specification with a buggy target
repository, visible tests, hidden (protected) tests, and a reference solution.

## Payment Webhook Benchmark

The built-in benchmark tests a FastAPI webhook that processes Stripe-like
payment events. The bug: the webhook creates a new payment record on every
call, even for duplicate `event_id` values. The fix requires:

1. A uniqueness constraint on `event_id` in the database
2. An upsert / find-or-create pattern in the webhook handler

### Structure

```
benchmarks/payment_webhook/
├── manifest.yaml          # Benchmark specification
├── goal.yaml              # Goal contract for the agent
├── source_repo/           # Buggy target repository
│   ├── src/
│   │   ├── app.py
│   │   └── database.py
│   ├── tests/
│   │   └── test_webhook.py
│   └── pyproject.toml
├── protected_tests/       # Hidden tests (mounted read-only)
│   └── test_idempotency.py
└── reference_solution/    # Correct implementation
    ├── src/
    │   ├── app.py
    │   └── database.py
    └── pyproject.toml
```

### Running

```bash
# With the scripted agent (applies reference solution)
uv run cah run --agent scripted --goal benchmarks/payment_webhook/manifest.yaml

# As a multi-run experiment
uv run cah experiment run --repetitions 5 --benchmark payment_webhook
```

### Visible Tests

`tests/test_webhook.py` — accessible to the agent during execution.
Tests basic webhook creation, status codes, and payload parsing.

### Hidden Tests

`protected_tests/test_idempotency.py` — mounted read-only in the sandbox,
never visible to the agent. Tests the core idempotency requirement:

```python
# Tests that duplicate event_ids return existing records
# rather than creating duplicates
def test_duplicate_event_id_returns_existing():
    response = client.post("/webhook", json=PAYLOAD)
    assert response.status_code == 200
    first_id = response.json()["id"]

    response = client.post("/webhook", json=PAYLOAD)
    assert response.status_code == 200
    second_id = response.json()["id"]
    assert first_id == second_id  # Must be the same record
```

## Creating a Custom Benchmark

1. Create a directory under `benchmarks/` with the structure above
2. Write a `goal.yaml` with the task description, constraints, and acceptance criteria
3. Create a `source_repo/` with the buggy code and visible tests
4. Create `protected_tests/` with hidden verification tests
5. Create `reference_solution/` with the correct implementation
6. Validate with:
   ```bash
   uv run python scripts/validate_benchmark.py benchmarks/your-benchmark/
   ```

### Manifest Format

```yaml
# manifest.yaml
benchmark_id: your-benchmark
title: "Your Benchmark Title"
description: "Description of the task"
model:
  provider: scriped
  name: scripted
target: source_repo/
acceptance:
  visible_tests:
    command: ["uv", "run", "pytest", "-q", "tests/"]
  hidden_tests:
    command: ["uv", "run", "pytest", "-q", "protected_tests/"]
  reference: reference_solution/
```
