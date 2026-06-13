"""Evaluator pipeline orchestration."""

from __future__ import annotations

from collections import defaultdict

from constrained_agent.domain.evaluations import EvaluationTier, EvaluationVector
from constrained_agent.errors import EvaluationError
from constrained_agent.evaluators.protocol import EvaluationContext, Evaluator

TIER_ORDER = (
    EvaluationTier.TIER_0_POLICY,
    EvaluationTier.TIER_1_FAST_STATIC,
    EvaluationTier.TIER_2_TARGETED_TESTS,
    EvaluationTier.TIER_3_FULL_TESTS,
    EvaluationTier.TIER_4_HIDDEN_AND_SECURITY,
)


class EvaluatorPipeline:
    """Run registered evaluators in tier order and combine their outcomes."""

    def __init__(self) -> None:
        self._evaluators: list[Evaluator] = []

    def register(self, evaluator: Evaluator) -> None:
        """Add an evaluator to the pipeline."""
        self._evaluators.append(evaluator)

    async def evaluate(self, context: EvaluationContext) -> EvaluationVector:
        """Run evaluators in tier order with short-circuiting on hard failures."""
        vector = EvaluationVector()
        by_tier: dict[EvaluationTier, list[Evaluator]] = defaultdict(list)
        for evaluator in self._evaluators:
            by_tier[evaluator.tier].append(evaluator)

        for tier in TIER_ORDER:
            for evaluator in by_tier.get(tier, []):
                result = await evaluator.evaluate(context)
                merge = getattr(evaluator, "merge_into", None)
                if callable(merge):
                    merge(vector, result)
                else:
                    vector.runtime_seconds += result.duration_seconds

                if tier is EvaluationTier.TIER_0_POLICY and not result.passed:
                    return vector
                if self._hard_gate_triggered(vector):
                    return vector
                if result.error is not None and result.exit_code is None:
                    raise EvaluationError(
                        f"evaluator '{result.evaluator_id}' failed: {result.error}"
                    )
        return vector

    @staticmethod
    def _hard_gate_triggered(vector: EvaluationVector) -> bool:
        return (
            vector.policy_violations > 0
            or vector.protected_file_changes > 0
            or vector.security_critical > 0
        )
