from __future__ import annotations

import sys

import pytest

from constrained_agent.errors import SandboxError
from constrained_agent.sandbox import ExecutionRequest, ExecutionResult, FakeSandbox


@pytest.mark.asyncio
async def test_fake_sandbox_returns_registered_result() -> None:
    sandbox = FakeSandbox()
    expected = ExecutionResult(
        stdout="ok\n",
        stderr="",
        exit_code=0,
        duration_seconds=0.01,
    )
    sandbox.register(["echo", "ok"], expected)

    result = await sandbox.execute(
        ExecutionRequest(argv=["echo", "ok"], purpose="test registered command")
    )

    assert result == expected
    assert sandbox.requests[0].argv == ["echo", "ok"]


@pytest.mark.asyncio
async def test_fake_sandbox_rejects_unregistered_command_by_default() -> None:
    sandbox = FakeSandbox()

    with pytest.raises(SandboxError, match="no fake sandbox result registered"):
        await sandbox.execute(
            ExecutionRequest(argv=["python", "-V"], purpose="missing registration")
        )


@pytest.mark.asyncio
async def test_fake_sandbox_can_fallback_to_local_subprocess() -> None:
    sandbox = FakeSandbox(allow_unregistered=True)

    result = await sandbox.execute(
        ExecutionRequest(
            argv=[sys.executable, "-c", "print('hello from fake sandbox')"],
            purpose="exercise subprocess fallback",
        )
    )

    assert result.exit_code == 0
    assert "hello from fake sandbox" in result.stdout
    assert result.timed_out is False
