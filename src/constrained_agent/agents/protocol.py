"""Agent protocol models for policy and controller integration."""

from __future__ import annotations

from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class FileEdit(BaseModel):
    """A structured file mutation proposed by an agent."""

    model_config = ConfigDict(extra="forbid")

    path: str = Field(min_length=1)
    operation: Literal["create", "replace", "patch", "delete"]
    content: str | None = None
    unified_diff: str | None = None

    @field_validator("path")
    @classmethod
    def _validate_path(cls, value: str) -> str:
        if value.strip() == "":
            raise ValueError("path must be a non-empty string")
        return value

    @model_validator(mode="after")
    def _validate_payload(self) -> FileEdit:
        if self.operation in {"create", "replace"}:
            if self.content is None:
                raise ValueError(f"{self.operation} edits require content")
            if self.unified_diff is not None:
                raise ValueError(f"{self.operation} edits must not include unified_diff")
        elif self.operation == "patch":
            if self.unified_diff is None:
                raise ValueError("patch edits require unified_diff")
        elif self.operation == "delete":
            if self.content is not None or self.unified_diff is not None:
                raise ValueError("delete edits must not include content or unified_diff")
        return self


class CommandRequest(BaseModel):
    """A structured sandbox command requested by an agent."""

    model_config = ConfigDict(extra="forbid")

    argv: list[str] = Field(min_length=1)
    purpose: str = Field(min_length=1)
    timeout_seconds: int = Field(gt=0, default=60)

    @field_validator("argv")
    @classmethod
    def _validate_argv(cls, value: list[str]) -> list[str]:
        if any(part.strip() == "" for part in value):
            raise ValueError("argv entries must be non-empty strings")
        return value


class ProposedCommand(BaseModel):
    """Backward-compatible command proposal model used by earlier policy tests."""

    model_config = ConfigDict(extra="forbid")

    argv: list[str] | str = Field(min_length=1)
    timeout_seconds: int = Field(gt=0, default=60)

    @field_validator("argv")
    @classmethod
    def _validate_compat_argv(cls, value: list[str] | str) -> list[str] | str:
        if isinstance(value, str):
            if value.strip() == "":
                raise ValueError("argv shell string must be non-empty")
            return value
        if any(part.strip() == "" for part in value):
            raise ValueError("argv entries must be non-empty strings")
        return value


class AgentProposal(BaseModel):
    """A bounded proposal produced by an agent iteration."""

    model_config = ConfigDict(extra="forbid")

    summary: str = Field(default="No summary provided.", min_length=1)
    hypothesis: str = Field(default="No hypothesis provided.", min_length=1)
    evidence_considered: list[str] = Field(default_factory=list)
    files_to_inspect: list[str] = Field(default_factory=list)
    edits: list[FileEdit] = Field(default_factory=list)
    commands: list[CommandRequest | ProposedCommand] = Field(default_factory=list)
    expected_effect: str = Field(default="No expected effect provided.", min_length=1)
    risk_notes: list[str] = Field(default_factory=list)
    completion_claimed: bool = False
    write_files: list[str] = Field(default_factory=list)
    diff: str = ""

    @field_validator(
        "evidence_considered",
        "files_to_inspect",
        "risk_notes",
        "write_files",
    )
    @classmethod
    def _validate_string_lists(cls, value: list[str]) -> list[str]:
        if any(item.strip() == "" for item in value):
            raise ValueError("list entries must be non-empty strings")
        return value


class AgentContext(BaseModel):
    """Fresh-session context passed into each agent iteration."""

    model_config = ConfigDict(extra="forbid")

    goal_summary: str = Field(min_length=1)
    repository_map: str = Field(min_length=1)
    candidate_diff: str = ""
    evaluation_failures: str = ""
    prior_rejected: str = ""
    remaining_budget: str = Field(min_length=1)
    permitted_actions: list[str] = Field(default_factory=list)
    protected_summary: str = Field(min_length=1)
    iteration: int = Field(ge=0)

    @field_validator("permitted_actions")
    @classmethod
    def _validate_permitted_actions(cls, value: list[str]) -> list[str]:
        if any(item.strip() == "" for item in value):
            raise ValueError("permitted_actions entries must be non-empty strings")
        return value


class CodingAgent(Protocol):
    """Protocol for coding agents that emit structured proposals."""

    async def propose_action(self, context: AgentContext) -> AgentProposal:
        """Return the next proposed action bundle."""

    def get_model_info(self) -> dict[str, str | int | float | bool | None]:
        """Return model metadata for evidence and auditing."""
