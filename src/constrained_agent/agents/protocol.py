"""Agent protocol models for policy and controller integration."""

from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProposedCommand(BaseModel):
    """A structured command proposal executed as an argv array."""

    model_config = ConfigDict(extra="forbid")

    argv: list[str] | str = Field(min_length=1)
    timeout_seconds: int = Field(gt=0, default=60)

    @field_validator("argv")
    @classmethod
    def _validate_argv(cls, value: list[str] | str) -> list[str] | str:
        if isinstance(value, str):
            if not value.strip():
                raise ValueError("argv shell string must be non-empty")
            return value
        if any(not part.strip() for part in value):
            raise ValueError("argv entries must be non-empty strings")
        return value


class AgentProposal(BaseModel):
    """A bounded proposal produced by an agent iteration."""

    model_config = ConfigDict(extra="forbid")

    summary: str = ""
    commands: list[ProposedCommand] = Field(default_factory=list)
    write_files: list[str] = Field(default_factory=list)
    diff: str = ""

    @field_validator("write_files")
    @classmethod
    def _validate_write_files(cls, value: list[str]) -> list[str]:
        if any(not item.strip() for item in value):
            raise ValueError("write_files entries must be non-empty strings")
        return value


class CodingAgent(Protocol):
    """Protocol for coding agents that emit structured proposals."""

    def propose(self) -> AgentProposal:
        """Return the next proposed action bundle."""
