"""Approval gate metadata used by the policy engine."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from constrained_agent.domain.approvals import ApprovalGate


class ApprovalDefinition(BaseModel):
    """Human-readable requirements for a given approval gate."""

    model_config = ConfigDict(extra="forbid")

    gate: ApprovalGate
    description: str = Field(min_length=1)
    required_conditions: list[str] = Field(min_length=1)


class ApprovalRegistry:
    """Lookup table for supported approval gates."""

    def __init__(self) -> None:
        self._definitions: dict[ApprovalGate, ApprovalDefinition] = {
            ApprovalGate.DEPENDENCY_CHANGE: ApprovalDefinition(
                gate=ApprovalGate.DEPENDENCY_CHANGE,
                description="Dependency manifest or lockfile changes are proposed.",
                required_conditions=[
                    "Review the dependency diff and supply-chain risk.",
                    "Confirm the change is necessary for the task.",
                ],
            ),
            ApprovalGate.PUBLIC_API_CHANGE: ApprovalDefinition(
                gate=ApprovalGate.PUBLIC_API_CHANGE,
                description="Public API surface changes are proposed.",
                required_conditions=[
                    "Review the API compatibility impact.",
                    "Confirm downstream consumers are accounted for.",
                ],
            ),
            ApprovalGate.DATABASE_SCHEMA_CHANGE: ApprovalDefinition(
                gate=ApprovalGate.DATABASE_SCHEMA_CHANGE,
                description="Database schema changes are proposed.",
                required_conditions=[
                    "Review migration safety and rollback strategy.",
                    "Confirm data compatibility requirements are met.",
                ],
            ),
            ApprovalGate.SENSITIVE_FILE_CHANGE: ApprovalDefinition(
                gate=ApprovalGate.SENSITIVE_FILE_CHANGE,
                description="Sensitive or protected files are proposed for modification.",
                required_conditions=[
                    "Review the target file and blast radius.",
                    "Confirm the edit is explicitly authorized.",
                ],
            ),
        }

    def get(self, gate: ApprovalGate) -> ApprovalDefinition:
        """Return metadata for a supported approval gate."""
        return self._definitions[gate]

    def description_for(self, gate: ApprovalGate) -> str:
        """Return the human-readable description for a gate."""
        return self.get(gate).description
