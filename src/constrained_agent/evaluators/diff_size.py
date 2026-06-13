"""Evaluator enforcing diff size limits."""

# ruff: noqa: SIM103 — early-return pattern more readable here

from __future__ import annotations

import subprocess

from constrained_agent.domain.evaluations import EvaluationResult, EvaluationTier, EvaluationVector
from constrained_agent.evaluators.protocol import EvaluationContext


class DiffSizeEvaluator:
    """Check repository diff size against configurable limits."""

    def __init__(
        self,
        *,
        evaluator_id: str = "diff_size",
        tier: EvaluationTier = EvaluationTier.TIER_1_FAST_STATIC,
        max_added_lines: int | None = None,
        max_removed_lines: int | None = None,
        max_total_lines: int | None = None,
    ) -> None:
        self.id = evaluator_id
        self.tier = tier
        self._max_added_lines = max_added_lines
        self._max_removed_lines = max_removed_lines
        self._max_total_lines = max_total_lines

    async def evaluate(self, context: EvaluationContext) -> EvaluationResult:
        """Measure line additions and removals for the current workspace."""
        completed = subprocess.run(
            ["git", "diff", "--numstat"],
            cwd=context.workspace,
            capture_output=True,
            text=True,
            check=False,
        )
        added_lines = 0
        removed_lines = 0
        for line in completed.stdout.splitlines():
            columns = line.split("\t", maxsplit=2)
            if len(columns) < 2 or "-" in columns[:2]:
                continue
            added_lines += int(columns[0])
            removed_lines += int(columns[1])
        total_lines = added_lines + removed_lines
        passed = self._within_limits(added_lines, removed_lines, total_lines)
        summary = (
            f"added_lines={added_lines} removed_lines={removed_lines} total_lines={total_lines}"
        )
        return EvaluationResult(
            evaluator_id=self.id,
            tier=self.tier,
            passed=passed and completed.returncode == 0,
            stdout=summary,
            stderr=completed.stderr or None,
            exit_code=completed.returncode,
            duration_seconds=0.0,
            truncated=False,
            error=None if completed.returncode == 0 else "git diff --numstat failed",
        )

    def merge_into(self, vector: EvaluationVector, result: EvaluationResult) -> None:
        """Represent diff-size failures as policy violations."""
        if not result.passed:
            vector.policy_violations += 1

    def _within_limits(self, added_lines: int, removed_lines: int, total_lines: int) -> bool:
        if self._max_added_lines is not None and added_lines > self._max_added_lines:
            return False
        if self._max_removed_lines is not None and removed_lines > self._max_removed_lines:
            return False
        if self._max_total_lines is not None and total_lines > self._max_total_lines:
            return False
        return True
