"""Domain models and typed contracts."""

from constrained_agent.domain.contracts import GoalContract, ContractValidator
from constrained_agent.domain.runs import Run, RunStatus
from constrained_agent.domain.candidates import Candidate, CandidateStatus
from constrained_agent.domain.evaluations import EvaluationVector, EvaluationTier, EvaluationResult
from constrained_agent.domain.evidence import Evidence, ArtifactRef
from constrained_agent.domain.budgets import BudgetTracker, BudgetUsage
from constrained_agent.domain.approvals import Approval, ApprovalStatus, ApprovalGate
from constrained_agent.domain.events import Event, EventType, TransitionEvent

__all__ = [
    "GoalContract", "ContractValidator",
    "Run", "RunStatus",
    "Candidate", "CandidateStatus",
    "EvaluationVector", "EvaluationTier", "EvaluationResult",
    "Evidence", "ArtifactRef",
    "BudgetTracker", "BudgetUsage",
    "Approval", "ApprovalStatus", "ApprovalGate",
    "Event", "EventType", "TransitionEvent",
]
