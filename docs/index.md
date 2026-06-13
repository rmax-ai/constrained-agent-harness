# Constrained Agent Harness

A **reference implementation** of a verifiable, bounded autonomous software
engineering system. The harness treats autonomous coding as a **constrained
search** over repository states — every model proposal is validated against
policy, evaluated against benchmarks, and persisted to an auditable event
store before the next iteration begins.

## Why

Current autonomous coding agents operate with unbounded autonomy — they can
write arbitrary files, run arbitrary commands, and decide when they're done
with no external verification. This makes them unsuitable for:

- **Enterprise compliance** — no audit trail, no policy enforcement
- **Safety-critical systems** — no verification gate before changes take effect
- **Reproducible research** — no deterministic replay or benchmark harness

The Constrained Agent Harness solves this by inverting the control flow: the
**controller** decides, the **model** proposes, and every proposal is validated,
evaluated, and persisted before anything reaches the target repository.

## Key Principles

1. **The model never makes the authoritative completion decision.** The
   controller owns all decisions — ACCEPT, REJECT, ROLLBACK, RETRY, COMPLETE, FAIL.
2. **Every state transition is persisted.** The hash-chained event store
   provides a complete, tamper-evident audit trail.
3. **Context is reconstructed fresh per iteration.** No conversation history
   leaks between steps — every model invocation starts from a principled
   reconstruction of the current state.
4. **All evaluations are vectors, not scalars.** Evaluators produce typed
   vectors with visible/hidden test results, pass/fail counts, and runtime
   metrics.
5. **Deterministic verification.** The completion manifest includes artifact
   hashes, final evaluation vectors, and budget usage — anything that can be
   verified externally, is.

## Project Status

This is a **reference implementation** — it demonstrates the architecture and
provides a working benchmark (payment webhook idempotency), but is not
intended for production deployment. It ships with a scripted agent for
reproducible testing and a Google ADK adapter for live model integration.

## Quick Links

- [Getting Started](getting-started.md)
- [Architecture](architecture.md)
- [Domain Model](domain.md)
- [CLI Reference](cli.md)
