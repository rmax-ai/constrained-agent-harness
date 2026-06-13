"""Agent adapters and protocol definitions."""

from constrained_agent.agents.google_adk import GoogleAdkCodingAgent
from constrained_agent.agents.protocol import AgentProposal, CodingAgent
from constrained_agent.agents.replay import ReplayAgent
from constrained_agent.agents.scripted import ScriptedAgent

__all__ = [
    "AgentProposal",
    "CodingAgent",
    "GoogleAdkCodingAgent",
    "ReplayAgent",
    "ScriptedAgent",
]
