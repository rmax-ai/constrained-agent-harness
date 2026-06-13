# constrained-agent-harness

[![CI](https://github.com/rmax-ai/constrained-agent-harness/actions/workflows/ci.yml/badge.svg)](https://github.com/rmax-ai/constrained-agent-harness/actions/workflows/ci.yml)
![Python Version](https://img.shields.io/badge/python-3.13-blue)
![License](https://img.shields.io/badge/license-Apache--2.0-green)

**A reference harness for running coding agents as bounded, verifiable search over repository states.**

This repository implements the reference architecture described in
*"From Agentic Loops to Constrained Search: A Reference Architecture for
Verifiable Autonomous Software Engineering."*

## Problem

Conventional coding agents operate as indefinite conversations: a model
receives a task, iterates freely, and the human operator judges when the
result is acceptable. This approach conflates proposal with verification
and makes completion decisions opaque.

## Architectural Thesis

The system models coding as a **constrained transition process** over
repository states:

```
S_t --a_t--> S_t+1
```

The model proposes changes. The deterministic harness evaluates the resulting
state and decides whether to accept, reject, roll back, retry, branch, or
complete. The model never makes the authoritative completion decision.

## What This Repository Contains

- **State machine controller** — bounded execution with 7 transition decisions
- **Goal contracts** — typed YAML specifications of task bounds
- **Policy engine** — path, command, and dependency enforcement
- **Sandbox** — Docker-isolated command execution
- **Git-backed repository store** — immutable checkpoints with rollback
- **Evaluator pipeline** — tiered plugin-based quality and safety checks
- **Hidden verification** — protected tests invisible to the agent
- **Context reconstruction** — fresh-session context per iteration
- **Artifact store** — append-only SHA-256 hash chain evidence
- **Telemetry** — runtime gauges, structured logging, run summaries
- **Benchmark**: payment webhook idempotency

## Quick Start

```bash
# Install
uv sync

# Run the scripted benchmark demo (no API credentials required)
uv run cah run --agent scripted --goal benchmarks/payment_webhook/manifest.yaml

# Generate a report
uv run cah status <run-id>

# Run a multi-repetition experiment
uv run cah experiment run --repetitions 3
```

## Live Model Demo

```bash
export CAH_GOOGLE_API_KEY=your_key_here
uv run cah run --agent google-adk --goal benchmarks/payment_webhook/manifest.yaml
```

## CLI Reference

| Command | Description |
|---------|-------------|
| `cah run` | Execute a run against a goal |
| `cah status` | One-line run status |
| `cah report run` | Detailed run report |
| `cah report compare` | Side-by-side run comparison |
| `cah report experiment` | List all runs for an experiment mode |
| `cah experiment run` | Run multi-repetition experiment |
| `cah artifacts verify` | Verify artifact hash chain |
| `cah inspect` | Inspect runs, events, candidates |
| `cah db upgrade` | Run schema migrations |
| `cah doctor` | System health check |
| `cah init` | Initialize runtime directory |

## Project Structure

```
src/constrained_agent/
  cli/          — Typer CLI commands
  domain/       — Typed contracts and domain models
  controller/   — State machine and transition logic
  agents/       — Model adapters (ADK, scripted, replay)
  context/      — Fresh-session context reconstruction
  policy/       — Path, command, dependency enforcement
  sandbox/      — Docker and fake sandbox
  repository/   — Git-backed repository store
  evaluators/   — Quality and safety check pipeline
  persistence/  — SQLite event store (SQLAlchemy + Alembic)
  artifacts/    — Evidence and hash chain
  reporting/    — Run and experiment reports
  telemetry/    — Runtime gauges, logging, run summaries
```

## Documentation

Full documentation at [docs/](docs/):

- [Architecture](docs/architecture.md)
- [Getting Started](docs/getting-started.md)
- [Domain Model](docs/domain.md)
- [Benchmarks](docs/benchmarks.md)
- [CLI Reference](docs/cli.md)

## License

Apache 2.0
