"""Command-backed evaluator implementation."""

from __future__ import annotations

from typing import Literal

from constrained_agent.domain.evaluations import EvaluationResult, EvaluationTier, EvaluationVector
from constrained_agent.errors import EvaluationError
from constrained_agent.evaluators.protocol import EvaluationContext
from constrained_agent.sandbox.protocol import ExecutionRequest

CommandOutcome = Literal[
    "compilation_ok",
    "type_check_ok",
    "lint_ok",
    "visible_tests",
    "hidden_tests",
    "policy_violations",
]


class CommandEvaluator:
    """Execute a single command in the sandbox and normalize the result."""

    def __init__(
        self,
        *,
        evaluator_id: str,
        tier: EvaluationTier,
        argv: list[str],
        purpose: str,
        expected_exit_code: int = 0,
        outcome: CommandOutcome | None = None,
    ) -> None:
        self.id = evaluator_id
        self.tier = tier
        self._argv = list(argv)
        self._purpose = purpose
        self._expected_exit_code = expected_exit_code
        self._outcome = outcome

    async def evaluate(self, context: EvaluationContext) -> EvaluationResult:
        """Run the configured command in the provided sandbox."""
        if context.sandbox is None:
            raise EvaluationError(f"evaluator '{self.id}' requires a sandbox")
        execution = await context.sandbox.execute(
            ExecutionRequest(
                argv=self._argv,
                purpose=self._purpose,
                timeout_seconds=context.goal.constraints.max_runtime_seconds,
                working_dir=str(context.workspace),
            )
        )
        passed = execution.exit_code == self._expected_exit_code and not execution.timed_out
        return EvaluationResult(
            evaluator_id=self.id,
            tier=self.tier,
            passed=passed,
            stdout=execution.stdout,
            stderr=execution.stderr,
            exit_code=execution.exit_code,
            duration_seconds=execution.duration_seconds,
            truncated=execution.truncated,
            error="command timed out" if execution.timed_out else None,
        )

    def merge_into(self, vector: EvaluationVector, result: EvaluationResult) -> None:
        """Project this evaluator's result into the normalized vector."""
        vector.runtime_seconds += result.duration_seconds
        if self._outcome == "compilation_ok":
            vector.compilation_ok = result.passed
        elif self._outcome == "type_check_ok":
            vector.type_check_ok = result.passed
        elif self._outcome == "lint_ok":
            vector.lint_ok = result.passed
        elif self._outcome == "visible_tests":
            if result.passed:
                vector.visible_tests_passed += 1
            else:
                vector.visible_tests_failed += 1
        elif self._outcome == "hidden_tests":
            vector.hidden_tests_passed = (vector.hidden_tests_passed or 0) + int(result.passed)
            vector.hidden_tests_failed = (vector.hidden_tests_failed or 0) + int(not result.passed)
        elif self._outcome == "policy_violations" and not result.passed:
            vector.policy_violations += 1
