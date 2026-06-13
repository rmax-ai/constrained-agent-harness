"""Readable summaries for evaluator failures."""

from __future__ import annotations

from collections import defaultdict

from constrained_agent.domain.evaluations import EvaluationResult, EvaluationVector


class FailureSummary:
    """Format evaluation failures into agent-readable context."""

    def __init__(self, *, max_output_chars: int = 400) -> None:
        self._max_output_chars = max_output_chars

    def summarize(
        self,
        evaluation_vector: EvaluationVector,
        evaluation_results: list[EvaluationResult],
    ) -> str:
        """Summarize failing checks grouped by evaluation tier."""
        lines = [
            "Evaluation vector:",
            (
                f"policy_violations={evaluation_vector.policy_violations}, "
                f"protected_file_changes={evaluation_vector.protected_file_changes}, "
                f"visible_tests_failed={evaluation_vector.visible_tests_failed}, "
                f"hidden_tests_failed={evaluation_vector.hidden_tests_failed}, "
                f"security_critical={evaluation_vector.security_critical}, "
                f"security_high={evaluation_vector.security_high}"
            ),
        ]
        failing_results = [result for result in evaluation_results if not result.passed]
        if not failing_results:
            lines.append("No failing evaluator details recorded.")
            return "\n".join(lines)

        grouped: dict[str, list[EvaluationResult]] = defaultdict(list)
        for result in failing_results:
            grouped[result.tier.value].append(result)

        for tier in sorted(grouped):
            lines.append(f"{tier}:")
            for result in grouped[tier]:
                detail = self._detail(result)
                exit_text = (
                    f", exit_code={result.exit_code}" if result.exit_code is not None else ""
                )
                lines.append(f"- {result.evaluator_id}{exit_text}: {detail}")
        return "\n".join(lines)

    def _detail(self, result: EvaluationResult) -> str:
        for label, value in (
            ("stderr", result.stderr),
            ("stdout", result.stdout),
            ("error", result.error),
        ):
            if value:
                compact = " ".join(value.split())
                if len(compact) > self._max_output_chars:
                    compact = compact[: self._max_output_chars - 3] + "..."
                return f"{label}={compact}"
        return "failed without additional output"
