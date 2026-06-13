"""Typed exception hierarchy for the constrained agent harness."""

from __future__ import annotations


class CahError(Exception):
    """Base exception for all CAH errors."""


class ConfigurationError(CahError):
    """Invalid or missing configuration."""


class GoalValidationError(CahError):
    """Goal contract failed validation."""


class ModelUnavailableError(CahError):
    """Requested model is not available or cannot be reached."""


class PolicyViolationError(CahError):
    """An action was rejected by the policy engine."""


class SandboxError(CahError):
    """Sandbox execution failed."""


class EvaluationError(CahError):
    """An evaluator failed to produce a result."""


class RepositoryStateError(CahError):
    """Repository state operation failed."""


class BudgetExceededError(CahError):
    """A budget limit was exceeded."""


class InvalidTransitionError(CahError):
    """An invalid state transition was attempted."""


class ArtifactIntegrityError(CahError):
    """Artifact hash verification failed."""


class ApprovalRequiredError(CahError):
    """Human approval is required before proceeding."""


class StagnationError(CahError):
    """Stagnation detected — no progress across iterations."""


class BenchmarkError(CahError):
    """Benchmark validation or execution error."""
