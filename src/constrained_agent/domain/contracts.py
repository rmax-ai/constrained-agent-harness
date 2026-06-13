"""Typed goal contract models for bounded agent execution."""

from __future__ import annotations

from enum import StrEnum
from hashlib import sha256

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator


class RevealFailuresMode(StrEnum):
    """How much hidden-check failure detail may be shown to the agent."""

    NONE = "NONE"
    SUMMARY_ONLY = "SUMMARY_ONLY"
    FULL = "FULL"


class NetworkMode(StrEnum):
    """Allowed network posture for a run."""

    OFF = "off"
    SANDBOX_DEFAULT = "sandbox_default"
    ON = "on"


class DependencyPolicy(StrEnum):
    """How dependency changes are governed."""

    FROZEN = "frozen"
    ALLOWLIST_ONLY = "allowlist_only"
    ALLOW_ALL = "allow_all"


class ContextStrategy(StrEnum):
    """How controller context is reconstructed per iteration."""

    FULL = "full"
    DIFF = "diff"
    MINIMAL = "minimal"


class CompletionStrategy(StrEnum):
    """How completion is evaluated."""

    CONTROLLER_DECIDES = "controller_decides"
    CONTROLLER_VERIFIED = "controller_verified"


class CheckpointStrategy(StrEnum):
    """When repository checkpoints are taken."""

    PER_ITERATION = "per_iteration"
    ON_CHANGE = "on_change"
    MANUAL = "manual"


class TaskDef(BaseModel):
    """Human-meaningful task metadata."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)


class ModelConfig(BaseModel):
    """Model selection and sampling controls."""

    model_config = ConfigDict(extra="forbid")

    provider: str = Field(min_length=1)
    name: str = Field(min_length=1)
    temperature: float = Field(ge=0.0, le=2.0, default=0.0)


class CheckDef(BaseModel):
    """A visible acceptance check."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    evaluator: str = Field(min_length=1)
    command: list[str] = Field(min_length=1)
    expected_exit_code: int = 0
    blocking: bool = True

    @field_validator("command")
    @classmethod
    def _validate_command(cls, value: list[str]) -> list[str]:
        if any(not part.strip() for part in value):
            raise ValueError("command entries must be non-empty strings")
        return value


class HiddenCheckConfig(BaseModel):
    """Configuration for hidden evaluator inputs."""

    model_config = ConfigDict(extra="forbid")

    directory: str = Field(min_length=1)
    writable: bool = False
    reveal_failures_to_agent: RevealFailuresMode = RevealFailuresMode.NONE

    @field_validator("writable")
    @classmethod
    def _validate_writable(cls, value: bool) -> bool:
        if value:
            raise ValueError("hidden checks must remain read-only")
        return value


class AcceptanceConfig(BaseModel):
    """Acceptance criteria for task completion."""

    model_config = ConfigDict(extra="forbid")

    required_checks: list[CheckDef] = Field(default_factory=list)
    hidden_checks: HiddenCheckConfig | None = None


class ConstraintConfig(BaseModel):
    """Execution limits and policy constraints."""

    model_config = ConfigDict(extra="forbid")

    max_iterations: int = Field(gt=0)
    max_runtime_seconds: int = Field(gt=0)
    max_model_calls: int = Field(gt=0)
    writable_paths: list[str] = Field(default_factory=list)
    protected_paths: list[str] = Field(default_factory=list)
    allowed_commands: list[list[str]] = Field(default_factory=list)
    forbidden_patterns: list[str] = Field(default_factory=list)
    network_mode: NetworkMode = NetworkMode.OFF
    dependency_policy: DependencyPolicy = DependencyPolicy.FROZEN

    @field_validator("writable_paths", "protected_paths", "forbidden_patterns")
    @classmethod
    def _validate_string_list(cls, value: list[str]) -> list[str]:
        if any(not item.strip() for item in value):
            raise ValueError("list entries must be non-empty strings")
        return value

    @field_validator("allowed_commands")
    @classmethod
    def _validate_allowed_commands(cls, value: list[list[str]]) -> list[list[str]]:
        for command in value:
            if not command:
                raise ValueError("allowed command entries must not be empty")
            if any(not part.strip() for part in command):
                raise ValueError("allowed command entries must contain non-empty strings")
        return value


class TerminationConfig(BaseModel):
    """Controller-owned run termination criteria."""

    model_config = ConfigDict(extra="forbid")

    success_conditions: list[str] = Field(default_factory=list)
    failure_conditions: list[str] = Field(default_factory=list)

    @field_validator("success_conditions", "failure_conditions")
    @classmethod
    def _validate_conditions(cls, value: list[str]) -> list[str]:
        if any(not item.strip() for item in value):
            raise ValueError("termination conditions must be non-empty strings")
        return value


class ExperimentConfig(BaseModel):
    """Experiment tuning for controller behavior."""

    model_config = ConfigDict(extra="forbid")

    context_strategy: ContextStrategy = ContextStrategy.FULL
    completion_strategy: CompletionStrategy = CompletionStrategy.CONTROLLER_DECIDES
    checkpoint_strategy: CheckpointStrategy = CheckpointStrategy.PER_ITERATION
    branching_factor: int = Field(ge=1, default=1)


class GoalContract(BaseModel):
    """Top-level typed goal contract."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(min_length=1)
    task: TaskDef
    model: ModelConfig
    acceptance: AcceptanceConfig
    constraints: ConstraintConfig
    approval_gates: list[str] = Field(default_factory=list)
    termination: TerminationConfig
    experiment: ExperimentConfig

    @field_validator("approval_gates")
    @classmethod
    def _validate_approval_gates(cls, value: list[str]) -> list[str]:
        if any(not item.strip() for item in value):
            raise ValueError("approval gates must be non-empty strings")
        return value

    def hash(self) -> str:
        """Return a SHA-256 hash of the canonical YAML serialization."""
        canonical_yaml = yaml.safe_dump(
            self.model_dump(mode="json"),
            sort_keys=True,
            default_flow_style=False,
            allow_unicode=False,
        )
        return sha256(canonical_yaml.encode("utf-8")).hexdigest()


class ContractValidator:
    """Cross-field validator for goal contracts."""

    @classmethod
    def validate(cls, goal: GoalContract) -> list[str]:
        """Return actionable validation messages."""
        errors: list[str] = []

        check_ids = [check.id for check in goal.acceptance.required_checks]
        duplicates = sorted({cid for cid in check_ids if check_ids.count(cid) > 1})
        for cid in duplicates:
            errors.append(
                f"required_checks contains duplicate id '{cid}'; make each check id unique"
            )

        if goal.constraints.max_model_calls < goal.constraints.max_iterations:
            errors.append(
                "constraints.max_model_calls is lower than max_iterations; "
                "increase max_model_calls or reduce iterations"
            )

        for writable_path in goal.constraints.writable_paths:
            for protected_path in goal.constraints.protected_paths:
                if cls._paths_overlap(writable_path, protected_path):
                    errors.append(
                        f"path overlap between writable '{writable_path}' "
                        f"and protected '{protected_path}'; "
                        "separate these path sets"
                    )

        hidden_checks = goal.acceptance.hidden_checks
        if (
            hidden_checks is not None
            and goal.constraints.protected_paths
            and not any(
                cls._paths_overlap(hidden_checks.directory, protected_path)
                for protected_path in goal.constraints.protected_paths
            )
        ):
            errors.append(
                "acceptance.hidden_checks.directory is not covered by "
                "constraints.protected_paths; "
                "mark hidden checks as protected"
            )

        if not goal.acceptance.required_checks and hidden_checks is None:
            errors.append("acceptance must define at least one required or hidden check")

        if not goal.termination.success_conditions:
            errors.append("termination.success_conditions must not be empty")

        if goal.experiment.branching_factor > 1 and goal.constraints.max_iterations < 2:
            errors.append(
                "experiment.branching_factor > 1 requires more than one iteration; "
                "increase max_iterations or reduce branching_factor"
            )

        return errors

    @staticmethod
    def _paths_overlap(left: str, right: str) -> bool:
        normalized_left = left.strip("/")
        normalized_right = right.strip("/")
        if not normalized_left or not normalized_right:
            return normalized_left == normalized_right
        return (
            normalized_left == normalized_right
            or normalized_left.startswith(f"{normalized_right}/")
            or normalized_right.startswith(f"{normalized_left}/")
        )
