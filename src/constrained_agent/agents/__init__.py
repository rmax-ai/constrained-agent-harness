"""Agent adapters and protocol definitions."""

from constrained_agent.agents.protocol import CodingAgent, AgentProposal
from constrained_agent.agents.google_adk import GoogleAdkCodingAgent
from constrained_agent.agents.scripted import ScriptedAgent
from constrained_agent.agents.replay import ReplayAgent

__all__ = [
    "CodingAgent", "AgentProposal",
    "GoogleAdkCodingAgent",
    "ScriptedAgent",
    "ReplayAgent",
]
