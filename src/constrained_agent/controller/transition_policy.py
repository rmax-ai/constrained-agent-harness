"""Deterministic transition policy for controller decisions."""

from __future__ import annotations

from constrained_agent.domain.candidates import Candidate
from constrained_agent.domain.contracts import GoalContract
from constrained_agent.domain.evaluations import EvaluationVector
from constrained_agent.domain.events import TransitionDecision


class TransitionPolicy:
    """Choose the next controller decision from evaluation evidence."""

    def decide(
        self,
        vector: EvaluationVector,
        contract: GoalContract,
        history: list[Candidate],
        *,
        completion_claimed: bool = False,
        execution_failed: bool = False,
        policy_violated: bool = False,
    ) -> TransitionDecision:
        """Return the next deterministic transition decision."""
        if policy_violated:
            return TransitionDecision.REJECT
        if execution_failed:
            return TransitionDecision.ROLLBACK
        if completion_claimed and vector.is_acceptable(contract):
            return TransitionDecision.COMPLETE
        if vector.is_acceptable(contract):
            return TransitionDecision.ACCEPT
        if self._is_stagnating(vector, history):
            return TransitionDecision.ROLLBACK
        return TransitionDecision.RETRY

    @staticmethod
    def _is_stagnating(vector: EvaluationVector, history: list[Candidate]) -> bool:
        scored_history = [candidate for candidate in history if candidate.evaluation is not None]
        if len(scored_history) < 2:
            return False
        previous = scored_history[-1].evaluation
        assert previous is not None
        if vector.is_better_than(previous):
            return False
        return scored_history[-1].repository_state_hash == scored_history[-2].repository_state_hash
