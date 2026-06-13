# Getting Started

## Prerequisites

- **Python 3.13+**
- **uv** (package manager) — install via `curl -LsSf https://astral.sh/uv/install.sh | sh`
- **Docker** (optional, for sandbox execution)
- **Git** (required for repository state management)

## Installation

```bash
# Clone the repository
git clone https://github.com/rmax-ai/constrained-agent-harness.git
cd constrained-agent-harness

# Install dependencies
uv sync

# Initialize the runtime directory
uv run cah init
```

## Running the Benchmark

The fastest way to see the system in action is to run the built-in payment
webhook benchmark with the scripted agent:

```bash
uv run cah run --agent scripted --goal benchmarks/payment_webhook/manifest.yaml
```

This runs a scripted agent that applies a known idempotency fix against a
buggy FastAPI webhook, validates it against visible tests, and produces a
completion manifest.

## Understanding the Output

After a run completes, use the reporting commands:

```bash
# List runs
uv run cah report list

# Detailed run report
uv run cah report run <run-id>

# One-line status
uv run cah status <run-id>
```

## Running an Experiment

Repeat the benchmark multiple times with statistical aggregation:

```bash
uv run cah experiment run --repetitions 3 --benchmark payment_webhook
```

## Running with a Live Model

To use the Google ADK adapter with Gemini 3.5 Flash:

```bash
export CAH_GOOGLE_API_KEY="your-api-key"
uv run cah run --agent google-adk --goal benchmarks/payment_webhook/manifest.yaml
```

## Running Tests

```bash
# All tests
uv run pytest

# Fast unit tests only
uv run pytest tests/unit -v

# Integration tests (requires database)
uv run pytest tests/integration -v

# Live model tests (requires CAH_GOOGLE_API_KEY)
uv run pytest -m live_model -v
```

## CLI Overview

See the [CLI Reference](cli.md) for a complete command listing.
