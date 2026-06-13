"""Fake sandbox implementation for deterministic tests."""

from __future__ import annotations

import asyncio
import shlex
from time import perf_counter

from constrained_agent.errors import SandboxError
from constrained_agent.sandbox.protocol import ExecutionRequest, ExecutionResult, Sandbox


class FakeSandbox(Sandbox):
    """Return registered results or optionally execute commands locally."""

    def __init__(self, *, allow_unregistered: bool = False) -> None:
        self._registered: dict[str, ExecutionResult] = {}
        self._allow_unregistered = allow_unregistered
        self.requests: list[ExecutionRequest] = []

    def register(self, script: list[str], result: ExecutionResult) -> None:
        """Register a deterministic response for an argv command."""
        self._registered[self._key(script)] = result.model_copy(deep=True)

    async def execute(self, request: ExecutionRequest) -> ExecutionResult:
        """Return a registered result or run the command with asyncio subprocesses."""
        self.requests.append(request.model_copy(deep=True))
        key = self._key(request.argv)
        if key in self._registered:
            return self._registered[key].model_copy(deep=True)
        if not self._allow_unregistered:
            raise SandboxError(f"no fake sandbox result registered for command: {key}")

        started_at = perf_counter()
        try:
            process = await asyncio.create_subprocess_exec(
                *request.argv,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=request.env,
                cwd=request.working_dir,
            )
            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    process.communicate(),
                    timeout=request.timeout_seconds,
                )
                timed_out = False
            except TimeoutError:
                process.kill()
                stdout_bytes, stderr_bytes = await process.communicate()
                timed_out = True
        except OSError as exc:
            raise SandboxError(str(exc)) from exc

        return ExecutionResult(
            stdout=stdout_bytes.decode("utf-8", errors="replace"),
            stderr=stderr_bytes.decode("utf-8", errors="replace"),
            exit_code=process.returncode if process.returncode is not None else -1,
            duration_seconds=perf_counter() - started_at,
            timed_out=timed_out,
            truncated=False,
            container_image=None,
        )

    async def close(self) -> None:
        """Release fake sandbox resources."""
        return None

    @staticmethod
    def _key(script: list[str]) -> str:
        return shlex.join(script)
