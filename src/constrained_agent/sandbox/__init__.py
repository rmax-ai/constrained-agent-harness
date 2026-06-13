"""Sandbox interfaces and implementations."""

from constrained_agent.sandbox.fake import FakeSandbox
from constrained_agent.sandbox.protocol import ExecutionRequest, ExecutionResult, Sandbox

__all__ = [
    "ExecutionRequest",
    "ExecutionResult",
    "FakeSandbox",
    "Sandbox",
]

try:
    from constrained_agent.sandbox.docker import DockerSandbox  # noqa: F401

    __all__.append("DockerSandbox")
except ImportError:
    pass
