"""Structured JSON logging for the controller loop."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger("cah.telemetry")


class TelemetryLogger:
    """Structured event logger for the controller loop.

    Writes JSON lines with standardised fields so they can be parsed,
    indexed, or replayed later.
    """

    def __init__(self, run_id: str) -> None:
        self._run_id = run_id

    def _log(self, event: str, **fields: Any) -> None:
        payload: dict[str, Any] = {
            "ts": datetime.now(UTC).isoformat(),
            "run_id": self._run_id,
            "event": event,
        }
        payload.update(fields)
        logger.info(json.dumps(payload, default=str))

    def transition(
        self,
        iteration: int,
        decision: str,
        proposal_summary: str | None = None,
        eval_results: list[dict[str, Any]] | None = None,
        total_tokens: int = 0,
        **extra: Any,
    ) -> None:
        """Log a transition event."""
        self._log(
            "transition",
            iteration=iteration,
            decision=decision,
            summary=proposal_summary,
            evaluations=eval_results,
            total_tokens=total_tokens,
            **extra,
        )

    def model_call(self, iteration: int, tokens: int = 0, duration: float = 0.0) -> None:
        """Log a model invocation."""
        self._log(
            "model_call",
            iteration=iteration,
            tokens=tokens,
            duration_seconds=round(duration, 3),
        )

    def evaluator(
        self,
        iteration: int,
        name: str,
        passed: bool,
        tier: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Log an evaluator result."""
        self._log(
            "evaluator",
            iteration=iteration,
            evaluator=name,
            passed=passed,
            tier=tier,
            details=details,
        )

    def error(self, iteration: int, message: str, exc_info: str | None = None) -> None:
        """Log an error during the controller loop."""
        self._log("error", iteration=iteration, message=message, exception=exc_info)

    def info(self, iteration: int, message: str, **extra: Any) -> None:
        """Log a generic informational event."""
        self._log("info", iteration=iteration, message=message, **extra)
