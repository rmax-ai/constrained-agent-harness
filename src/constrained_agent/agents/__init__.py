"""Agent adapters and protocol definitions."""

from __future__ import annotations

from constrained_agent.agents.protocol import AgentProposal, CodingAgent, ProposedCommand

__all__ = [
    "AgentProposal",
    "CodingAgent",
    "ProposedCommand",
]

try:
    from constrained_agent.agents.google_adk import GoogleAdkCodingAgent  # noqa: F401

    __all__.append("GoogleAdkCodingAgent")
except ImportError:
    pass

try:
    from constrained_agent.agents.scripted import ScriptedAgent  # noqa: F401

    __all__.append("ScriptedAgent")
except ImportError:
    pass

try:
    from constrained_agent.agents.replay import ReplayAgent  # noqa: F401

    __all__.append("ReplayAgent")
except ImportError:
    pass
