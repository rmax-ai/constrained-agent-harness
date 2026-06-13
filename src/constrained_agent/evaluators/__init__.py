"""Evaluator pipeline — plugins for quality and safety checks."""

from constrained_agent.domain.evaluations import EvaluationResult, EvaluationTier, EvaluationVector
from constrained_agent.evaluators.command import CommandEvaluator
from constrained_agent.evaluators.diff_size import DiffSizeEvaluator
from constrained_agent.evaluators.pipeline import EvaluatorPipeline
from constrained_agent.evaluators.protocol import (
    EvaluationContext,
    Evaluator,
)

__all__ = [
    "CommandEvaluator",
    "DiffSizeEvaluator",
    "EvaluationContext",
    "EvaluationResult",
    "EvaluationTier",
    "EvaluationVector",
    "Evaluator",
    "EvaluatorPipeline",
]
