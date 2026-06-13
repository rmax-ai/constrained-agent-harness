"""Domain models and typed contracts."""

from constrained_agent.domain.approvals import Approval, ApprovalGate, ApprovalStatus
from constrained_agent.domain.budgets import BudgetTracker, BudgetUsage
from constrained_agent.domain.candidates import Candidate, CandidateId, CandidateStatus
from constrained_agent.domain.contracts import ContractValidator, GoalContract
from constrained_agent.domain.evaluations import (
    EvaluationResult,
    EvaluationTier,
    EvaluationVector,
)
from constrained_agent.domain.events import Event, EventType, TransitionDecision, TransitionEvent
from constrained_agent.domain.evidence import ArtifactRef, Evidence
from constrained_agent.domain.runs import Run, RunId, RunStatus

__all__ = [
    "Approval",
    "ApprovalGate",
    "ApprovalStatus",
    "ArtifactRef",
    "BudgetTracker",
    "BudgetUsage",
    "Candidate",
    "CandidateId",
    "CandidateStatus",
    "ContractValidator",
    "EvaluationResult",
    "EvaluationTier",
    "EvaluationVector",
    "Event",
    "EventType",
    "Evidence",
    "GoalContract",
    "Run",
    "RunId",
    "RunStatus",
    "TransitionDecision",
    "TransitionEvent",
]
