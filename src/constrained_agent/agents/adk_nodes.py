"""ADK workflow nodes for the coding-agent proposal pipeline."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from google.adk import workflow as adk
from pydantic import BaseModel, ConfigDict

from constrained_agent.agents.google_adk import GoogleAdkCodingAgent
from constrained_agent.agents.protocol import AgentContext, AgentProposal
from constrained_agent.context import ContextBuilder
from constrained_agent.domain.candidates import Candidate
from constrained_agent.domain.evidence import Evidence
from constrained_agent.domain.runs import Run
from constrained_agent.policy.engine import PolicyEngine, PolicyReport


class ProposalValidationResult(BaseModel):
    """Validated proposal plus the policy report used to judge it."""

    model_config = ConfigDict(extra="forbid")

    proposal: AgentProposal
    policy_report: PolicyReport


class PrepareContextNode(adk.FunctionNode):
    """Build fresh agent context for the next iteration."""

    def __init__(self, *, context_builder: ContextBuilder) -> None:
        self._context_builder = context_builder
        super().__init__(func=self._execute_for_workflow, name="prepare_context")

    async def execute(
        self,
        *,
        run: Run,
        candidate: Candidate,
        evidence: list[Evidence],
        stagnation_report: Any,
    ) -> AgentContext:
        """Build the bounded context payload."""
        return await self._context_builder.build(run, candidate, evidence, stagnation_report)

    async def _execute_for_workflow(
        self,
        run: Run,
        candidate: Candidate,
        evidence: list[Evidence],
        stagnation_report: Any = None,
    ) -> AgentContext:
        return await self.execute(
            run=run,
            candidate=candidate,
            evidence=evidence,
            stagnation_report=stagnation_report,
        )


class InvokeCodingAgentNode(adk.FunctionNode):
    """Invoke the live Google ADK coding agent."""

    def __init__(self, *, agent: GoogleAdkCodingAgent) -> None:
        self._agent = agent
        super().__init__(func=self._execute_for_workflow, name="invoke_agent")

    async def execute(self, *, context: AgentContext) -> AgentProposal:
        """Return the next structured coding proposal."""
        return await self._agent.propose_action(context)

    async def _execute_for_workflow(self, context: AgentContext) -> AgentProposal:
        return await self.execute(context=context)


class ValidateProposalNode(adk.FunctionNode):
    """Validate a proposal against the repository policy contract."""

    def __init__(self, *, policy_engine: PolicyEngine) -> None:
        self._policy_engine = policy_engine
        super().__init__(func=self._execute_for_workflow, name="validate")

    def execute(self, *, proposal: AgentProposal, workspace: Path) -> ProposalValidationResult:
        """Return the proposal together with its policy report."""
        report = self._policy_engine.check_proposal(proposal, workspace)
        return ProposalValidationResult(proposal=proposal, policy_report=report)

    def _execute_for_workflow(
        self,
        proposal: AgentProposal,
        workspace: Path,
    ) -> ProposalValidationResult:
        return self.execute(proposal=proposal, workspace=workspace)


def create_coding_agent_workflow(
    *,
    context_builder: ContextBuilder,
    agent: GoogleAdkCodingAgent,
    policy_engine: PolicyEngine,
) -> adk.Workflow:
    """Compose the coding-agent proposal workflow."""
    prepare = PrepareContextNode(context_builder=context_builder)
    invoke = InvokeCodingAgentNode(agent=agent)
    validate = ValidateProposalNode(policy_engine=policy_engine)
    return adk.Workflow(
        name="coding-agent",
        edges=[
            (adk.START, prepare),
            (prepare, invoke),
            (invoke, validate),
        ],
        output_schema=ProposalValidationResult,
    )


__all__ = [
    "InvokeCodingAgentNode",
    "PrepareContextNode",
    "ProposalValidationResult",
    "ValidateProposalNode",
    "create_coding_agent_workflow",
]
