# Phase 5: Telemetry, Reporting & Documentation

Implement three remaining layers:

## 5.1 Telemetry

Create `src/constrained_agent/telemetry/` with:

- `gauge.py` — lightweight runtime gauges (iteration count, elapsed, decision frequency, pending/blocked determiners). Tracked in-memory, flushed on transition.
- `logger.py` — structured JSON logging for the controller loop. Every transition logs: iteration, decision, agent_proposal summary, eval results, new total tokens, timestamps. Use Python stdlib `logging` (not structlog or external deps).
- `run_summary.py` — `RunSummary` Pydantic model that aggregates: duration, total iterations, decisions per type, evaluator pass/fail counts, final approval status, artifact count, total token estimate. Build from the last event in the event store.

## 5.2 CLI Enhancements (reporting commands)

Extend the `cah` CLI in `src/constrained_agent/cli/app.py`:

- `cah report run <run_id>` — print a formatted summary table (Rich): run id, status, iterations, duration, decisions breakdown, total tokens. Use `RunSummary` from telemetry.
- `cah report experiment <exp_id>` — table of all runs in the experiment, sorted by iteration count, with pass/fail/avg tokens columns.
- `cah report compare <run_id_a> <run_id_b>` — side-by-side comparison of two runs (iterations, decisions, eval vectors, artifacts).
- Ensure all CLI report commands handle missing data gracefully (print "not found").
- Add a `cah run status <run_id>` shorthand that prints a single-line status.

## 5.3 MkDocs Documentation Scaffold

- Create `docs/index.md` — project overview, architecture diagram (ASCII), key concepts.
- Create `docs/getting-started.md` — installation (uv), running the benchmark, CLI commands.
- Create `docs/architecture.md` — system architecture with component descriptions and data flow (Mermaid diagram if possible, ASCII fallback).
- Create `docs/domain.md` — core domain model descriptions (contracts, runs, candidates, evaluations, state machine).
- Create `docs/benchmarks.md` — how to create a benchmark, manifest format, protected tests.
- Create `docs/cli.md` — full CLI reference with examples.
- Create `mkdocs.yml` at repo root — Material theme, nav order matching above, `site_name: "Constrained Agent Harness"`.

## Verification

1. `uv run pytest tests/ -q` — all existing tests still pass
2. `uv run ruff check src/`
3. `uv run mkdocs build --strict` (only if mkdocs + theme are available; skip if not)
4. `python -c "from constrained_agent.telemetry.run_summary import RunSummary; print('telemetry OK')"` — imports work
