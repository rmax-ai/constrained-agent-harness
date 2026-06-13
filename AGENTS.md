# AGENTS.md — for AI coding assistants

## Project

constrained-agent-harness — a reference harness for verifiable autonomous
software engineering.

## Architecture

The system is built as a **constrained transition process** over repository
states. The controller owns all decisions; the model proposes changes.

### Key Boundaries

- **Controller** (`src/constrained_agent/controller/`) — state machine,
  transition decisions, termination. This is the authoritative runtime.
- **Domain** (`src/constrained_agent/domain/`) — typed contracts and models.
  No infrastructure dependencies.
- **Policy** (`src/constrained_agent/policy/`) — path, command, dependency
  enforcement. Pure functions, no side effects.
- **Sandbox** (`src/constrained_agent/sandbox/`) — isolated execution via
  Docker. Protocol + Docker implementation + fake for tests.
- **Repository** (`src/constrained_agent/repository/`) — Git-backed immutable
  state. Checkpoint, restore, diff.
- **Evaluators** (`src/constrained_agent/evaluators/`) — plugin pipeline for
  quality and safety checks. Tiered execution order.
- **Agents** (`src/constrained_agent/agents/`) — model adapters. ADK,
  scripted (deterministic), replay (for testing).
- **Context** (`src/constrained_agent/context/`) — fresh-session context
  reconstruction. No conversation history.
- **Artifacts** (`src/constrained_agent/artifacts/`) — append-only hash chain
  evidence store.
- **Persistence** (`src/constrained_agent/persistence/`) — SQLite event store
  via SQLAlchemy + Alembic.

### Rules

1. The model NEVER makes the authoritative completion decision.
2. Every state transition is persisted before continuing.
3. Protected tests are mounted read-only in the sandbox.
4. Every command executes as argument arrays, never shell=True.
5. All evaluations are recorded as vectors, not scalars.
6. Context is reconstructed fresh per iteration — no conversation history.
7. The artifact store uses SHA-256 hash chains.

### File Conventions

- `src/constrained_agent/` — all source code
- `tests/unit/` — unit tests (no external dependencies)
- `tests/integration/` — integration tests (SQLite, Git, Docker)
- `tests/end_to_end/` — full pipeline tests
- `benchmarks/` — benchmark repositories
- `.cah/` — runtime directory (gitignored)
- `docs/` — MkDocs documentation

### Testing

```bash
uv run pytest                          # all tests
uv run pytest -m live_model            # requires Gemini API key
uv run pytest tests/unit -v            # fast unit tests
```

### Important

- Use `uv` for all Python operations (not pip)
- Python 3.13+
- `from __future__ import annotations` in all files
- Pydantic v2 for boundary validation
- No global state, no singletons, no service locator
- Constructor injection throughout
