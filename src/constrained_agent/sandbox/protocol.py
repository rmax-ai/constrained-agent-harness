"""Sandbox execution contracts."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ExecutionRequest(BaseModel):
    """A structured command execution request."""

    model_config = ConfigDict(extra="forbid")

    argv: list[str] = Field(min_length=1)
    purpose: str = Field(min_length=1)
    timeout_seconds: int = Field(gt=0, default=60)
    env: dict[str, str] | None = None
    working_dir: str | None = None

    @field_validator("argv")
    @classmethod
    def _validate_argv(cls, value: list[str]) -> list[str]:
        if any(part.strip() == "" for part in value):
            raise ValueError("argv entries must be non-empty strings")
        return value


class ExecutionResult(BaseModel):
    """Normalized output captured from sandbox command execution."""

    model_config = ConfigDict(extra="forbid")

    stdout: str = ""
    stderr: str = ""
    exit_code: int
    duration_seconds: float = Field(ge=0.0)
    timed_out: bool = False
    truncated: bool = False
    container_image: str | None = None


@runtime_checkable
class Sandbox(Protocol):
    """Async execution backend used by evaluators and controller logic."""

    async def execute(self, request: ExecutionRequest) -> ExecutionResult:
        """Run a single argv command request."""

    async def close(self) -> None:
        """Release sandbox resources."""
