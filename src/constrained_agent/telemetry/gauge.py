"""Lightweight runtime gauges tracked in-memory and flushed on transition."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass
class GaugeCollector:
    """In-memory counters and metrics for a single run.

    Attributes:
        iteration_count: Total iterations executed.
        start_time: UTC timestamp when the run started.
        decisions: Counter of decision types seen (ACCEPT, REJECT, ROLLBACK, etc.).
        evaluator_pass: Counter of evaluator passes by name.
        evaluator_fail: Counter of evaluator failures by name.
        pending_determiners: Number of determiners still pending.
        blocked_determiners: Number of determiners blocked.
        model_calls: Total model invocation count.
        total_token_estimate: Accumulated token estimate across all model calls.
    """

    iteration_count: int = 0
    start_time: datetime = field(default_factory=lambda: datetime.now(UTC))
    decisions: Counter[str] = field(default_factory=Counter)
    evaluator_pass: Counter[str] = field(default_factory=Counter)
    evaluator_fail: Counter[str] = field(default_factory=Counter)
    pending_determiners: int = 0
    blocked_determiners: int = 0
    model_calls: int = 0
    total_token_estimate: int = 0

    def record_decision(self, decision: str) -> None:
        """Record a transition decision."""
        self.decisions[decision] += 1

    def record_evaluator(self, name: str, passed: bool) -> None:
        """Record an evaluator pass or fail."""
        if passed:
            self.evaluator_pass[name] += 1
        else:
            self.evaluator_fail[name] += 1

    def record_model_call(self, token_estimate: int = 0) -> None:
        """Record a model invocation with an optional token estimate."""
        self.model_calls += 1
        self.total_token_estimate += token_estimate

    def snapshot(self) -> dict[str, Any]:
        """Return a JSON-serialisable snapshot of current gauges."""
        elapsed = (datetime.now(UTC) - self.start_time).total_seconds()
        return {
            "iteration_count": self.iteration_count,
            "elapsed_seconds": round(elapsed, 2),
            "decisions": dict(self.decisions),
            "evaluator_passes": dict(self.evaluator_pass),
            "evaluator_failures": dict(self.evaluator_fail),
            "pending_determiners": self.pending_determiners,
            "blocked_determiners": self.blocked_determiners,
            "model_calls": self.model_calls,
            "total_token_estimate": self.total_token_estimate,
        }

    def reset(self) -> None:
        """Reset all gauges to initial state."""
        self.iteration_count = 0
        self.start_time = datetime.now(UTC)
        self.decisions.clear()
        self.evaluator_pass.clear()
        self.evaluator_fail.clear()
        self.pending_determiners = 0
        self.blocked_determiners = 0
        self.model_calls = 0
        self.total_token_estimate = 0
