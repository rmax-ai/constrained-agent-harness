"""Evaluation domain models for the evaluator pipeline."""

# ruff: noqa: SIM103 - early-return pattern more readable here

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from constrained_agent.domain.contracts import DependencyPolicy, GoalContract


class EvaluationTier(StrEnum):
    """Execution tier for evaluator pipeline stages."""

    TIER_0_POLICY = "tier_0_policy"
    TIER_1_FAST_STATIC = "tier_1_fast_static"
    TIER_2_TARGETED_TESTS = "tier_2_targeted_tests"
    TIER_3_FULL_TESTS = "tier_3_full_tests"
    TIER_4_HIDDEN_AND_SECURITY = "tier_4_hidden_and_security"


class EvaluationVector(BaseModel):
    """Normalized evaluation summary used for candidate comparison."""

    model_config = ConfigDict(extra="forbid")

    policy_violations: int = Field(ge=0, default=0)
    protected_file_changes: int = Field(ge=0, default=0)
    compilation_ok: bool | None = None
    type_check_ok: bool | None = None
    lint_ok: bool | None = None
    visible_tests_passed: int = Field(ge=0, default=0)
    visible_tests_failed: int = Field(ge=0, default=0)
    hidden_tests_passed: int | None = Field(ge=0, default=None)
    hidden_tests_failed: int | None = Field(ge=0, default=None)
    security_critical: int = Field(ge=0, default=0)
    security_high: int = Field(ge=0, default=0)
    dependency_changes: int = Field(ge=0, default=0)
    runtime_seconds: float = Field(ge=0.0, default=0.0)

    @staticmethod
    def _check_rank(value: bool | None) -> int:
        if value is True:
            return 2
        if value is None:
            return 1
        return 0

    def is_better_than(self, other: EvaluationVector) -> bool:
        """Compare vectors lexicographically from hard gates to tiebreakers."""
        self_key = (
            self.policy_violations,
            self.protected_file_changes,
            self.security_critical,
            -self._check_rank(self.compilation_ok),
            -self._check_rank(self.type_check_ok),
            -self._check_rank(self.lint_ok),
            self.visible_tests_failed,
            self.hidden_tests_failed if self.hidden_tests_failed is not None else 0,
            self.security_high,
            -self.visible_tests_passed,
            -(self.hidden_tests_passed if self.hidden_tests_passed is not None else 0),
            self.dependency_changes,
            self.runtime_seconds,
        )
        other_key = (
            other.policy_violations,
            other.protected_file_changes,
            other.security_critical,
            -self._check_rank(other.compilation_ok),
            -self._check_rank(other.type_check_ok),
            -self._check_rank(other.lint_ok),
            other.visible_tests_failed,
            other.hidden_tests_failed if other.hidden_tests_failed is not None else 0,
            other.security_high,
            -other.visible_tests_passed,
            -(other.hidden_tests_passed if other.hidden_tests_passed is not None else 0),
            other.dependency_changes,
            other.runtime_seconds,
        )
        return self_key < other_key

    def is_acceptable(self, contract: GoalContract) -> bool:
        """Check whether this vector satisfies contract-backed hard gates."""
        if self.policy_violations > 0:
            return False
        if self.protected_file_changes > 0:
            return False
        if self.security_critical > 0:
            return False
        if self.visible_tests_failed > 0:
            return False
        if self.hidden_tests_failed is not None and self.hidden_tests_failed > 0:
            return False
        if self.compilation_ok is False:
            return False
        if self.type_check_ok is False:
            return False
        if self.lint_ok is False:
            return False
        if self.runtime_seconds > float(contract.constraints.max_runtime_seconds):
            return False
        if (
            contract.constraints.dependency_policy == DependencyPolicy.FROZEN
            and self.dependency_changes > 0
        ):
            return False
        return True


class EvaluationResult(BaseModel):
    """Detailed output from a single evaluator execution."""

    model_config = ConfigDict(extra="forbid")

    evaluator_id: str = Field(min_length=1)
    tier: EvaluationTier
    passed: bool
    stdout: str | None = None
    stderr: str | None = None
    exit_code: int | None = None
    duration_seconds: float = Field(ge=0.0)
    truncated: bool = False
    error: str | None = None
