"""Deterministic scripted agent for controller and pipeline tests."""

from __future__ import annotations

from collections.abc import Sequence

from constrained_agent.agents.protocol import AgentContext, AgentProposal, CodingAgent


class ScriptedAgent(CodingAgent):
    """Replay a pre-defined list of proposals without invoking a live model."""

    def __init__(
        self,
        proposals: Sequence[AgentProposal],
        *,
        model_info: dict[str, str | int | float | bool | None] | None = None,
    ) -> None:
        self._proposals = list(proposals)
        self._index = 0
        self._model_info = model_info or {
            "provider": "scripted",
            "model_identifier": "scripted-agent",
        }

    async def propose_action(self, context: AgentContext) -> AgentProposal:
        """Return the next scripted proposal in sequence."""
        del context
        if self._index >= len(self._proposals):
            raise RuntimeError("scripted agent has no remaining proposals")
        proposal = self._proposals[self._index]
        self._index += 1
        return proposal.model_copy(deep=True)

    def get_model_info(self) -> dict[str, str | int | float | bool | None]:
        """Expose deterministic metadata for the scripted source."""
        return dict(self._model_info)

    @classmethod
    def success(cls) -> ScriptedAgent:
        """Return a one-shot successful proposal."""
        return cls(
            [
                AgentProposal(
                    summary="Implement the requested change.",
                    hypothesis="A small code change resolves the task.",
                    evidence_considered=["deterministic test fixture"],
                    files_to_inspect=["src/example.py"],
                    edits=[],
                    commands=[],
                    expected_effect="Visible checks should pass.",
                    risk_notes=[],
                    completion_claimed=True,
                )
            ]
        )

    @classmethod
    def failure(cls) -> ScriptedAgent:
        """Return a proposal sequence representing an unsuccessful attempt."""
        return cls(
            [
                AgentProposal(
                    summary="Attempt a change that does not solve the task.",
                    hypothesis="The issue may be configuration-related.",
                    evidence_considered=["deterministic test fixture"],
                    files_to_inspect=["pyproject.toml"],
                    edits=[],
                    commands=[],
                    expected_effect="The attempted change may narrow the failure.",
                    risk_notes=["May not address the root cause."],
                    completion_claimed=False,
                )
            ]
        )

    @classmethod
    def policy_violation(cls) -> ScriptedAgent:
        """Return a proposal that intentionally violates execution policy."""
        return cls(
            [
                AgentProposal(
                    summary="Propose a forbidden command for policy testing.",
                    hypothesis="Policy enforcement should reject the command.",
                    evidence_considered=["deterministic test fixture"],
                    files_to_inspect=[],
                    edits=[],
                    commands=[
                        {
                            "argv": ["rm", "-rf", "/"],
                            "purpose": "simulate a forbidden command",
                            "timeout_seconds": 1,
                        }
                    ],
                    expected_effect="Controller should reject the proposal.",
                    risk_notes=["Intentional policy violation."],
                    completion_claimed=False,
                )
            ]
        )

    @classmethod
    def false_completion(cls) -> ScriptedAgent:
        """Return a proposal that incorrectly claims task completion."""
        return cls(
            [
                AgentProposal(
                    summary="Claim completion without performing corrective work.",
                    hypothesis="The bug may already be fixed.",
                    evidence_considered=["deterministic test fixture"],
                    files_to_inspect=[],
                    edits=[],
                    commands=[],
                    expected_effect="No material repository change.",
                    risk_notes=["False-positive completion claim."],
                    completion_claimed=True,
                )
            ]
        )

    @classmethod
    def regression(cls) -> ScriptedAgent:
        """Return a proposal that introduces risk of breaking behavior."""
        return cls(
            [
                AgentProposal(
                    summary="Change implementation in a way that may regress behavior.",
                    hypothesis="A broad rewrite could fix the issue quickly.",
                    evidence_considered=["deterministic test fixture"],
                    files_to_inspect=["src/example.py", "tests/test_example.py"],
                    edits=[],
                    commands=[],
                    expected_effect="Functional behavior may change in unrelated paths.",
                    risk_notes=["Potential regression in covered behavior."],
                    completion_claimed=False,
                )
            ]
        )
