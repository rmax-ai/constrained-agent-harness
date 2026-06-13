# constrained-agent-harness — Master Prompt

## Project

A reference harness for running coding agents as bounded, verifiable search over repository states. Implements the architecture from "From Agentic Loops to Constrained Search."

## Core Architecture

The system is a **constrained transition process**:

```
S_t + a_t → S_t+1
Controller evaluates → {ACCEPT, REJECT, ROLLBACK, RETRY, BRANCH, COMPLETE, FAIL}
```

The model proposes changes. The **deterministic harness** decides acceptance. The model never makes the authoritative completion decision.

## Non-Negotiable Rules

1. Model NEVER declares completion — only the controller does
2. Every state transition is persisted BEFORE continuing
3. Protected tests are mounted READ-ONLY in the sandbox — agent cannot modify them
4. Every command executes as argument arrays — NEVER shell=True
5. Evaluations are vectors, not scalars — hard gates prevent compensating failures
6. Context is reconstructed FRESH per iteration — no conversation history is sent to the model
7. Artifact store uses SHA-256 hash chains with previous-event hashing
8. `from __future__ import annotations` in every file
9. Python 3.13, Pydantic v2, no global state, no singletons, constructor injection

## Directory Structure

```
src/constrained_agent/
  cli/         — Typer CLI
  domain/      — Pure domain models (no infra deps)
  controller/  — State machine + orchestration
  agents/      — Model adapters (ADK, scripted, replay, failing)
  context/     — Fresh-session context builder
  policy/      — Path/command/dependency enforcement
  sandbox/     — Docker + fake sandbox
  repository/  — Git-backed state
  evaluators/  — Plugin pipeline
  persistence/ — SQLite + SQLAlchemy + Alembic
  artifacts/   — Hash chain evidence
  reporting/   — Run + experiment reports
```

## Current State

- Repo bootstrapped (pyproject.toml, CLI skeleton, settings, logging, errors, package structure)
- Phase 1 (Project Skeleton) — COMPLETE
- Phase 2 (Deterministic Core) — IN PROGRESS

## Repository

- GitHub: https://github.com/rmax-ai/constrained-agent-harness
- Issues: #3 = Phase 2
