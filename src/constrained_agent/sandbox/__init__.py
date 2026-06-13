"""Sandbox interfaces and implementations."""

from constrained_agent.sandbox.protocol import Sandbox, ExecutionRequest, ExecutionResult
from constrained_agent.sandbox.docker import DockerSandbox
from constrained_agent.sandbox.fake import FakeSandbox

__all__ = [
    "Sandbox", "ExecutionRequest", "ExecutionResult",
    "DockerSandbox",
    "FakeSandbox",
]
