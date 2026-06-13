from __future__ import annotations

import json

import pytest

from constrained_agent.agents import (
    AgentContext,
    AgentProposal,
    CommandRequest,
    FileEdit,
    ReplayAgent,
    ScriptedAgent,
)


def make_context() -> AgentContext:
    return AgentContext(
        goal_summary="Fix the failing test.",
        repository_map="src/ and tests/",
        candidate_diff="",
        evaluation_failures="",
        prior_rejected="",
        remaining_budget="2 iterations left",
        permitted_actions=["edit files", "run tests"],
        protected_summary="tests/protected is read-only",
        iteration=1,
    )


def make_proposal(*, completion_claimed: bool = False) -> AgentProposal:
    return AgentProposal(
        summary="Inspect the failing module and update the implementation.",
        hypothesis="A missing guard clause is causing the failure.",
        evidence_considered=["failing unit test", "stack trace"],
        files_to_inspect=["src/constrained_agent/example.py"],
        edits=[
            FileEdit(
                path="src/constrained_agent/example.py",
                operation="patch",
                content=None,
                unified_diff="@@ -1 +1 @@\n-old\n+new\n",
            )
        ],
        commands=[
            CommandRequest(
                argv=["uv", "run", "pytest", "tests/unit/test_example.py"],
                purpose="verify the targeted regression",
            )
        ],
        expected_effect="The failing unit test should pass after the guard is added.",
        risk_notes=["The guard may need adjustment for edge cases."],
        completion_claimed=completion_claimed,
    )


@pytest.mark.asyncio
async def test_scripted_agent_returns_proposals_in_order() -> None:
    first = make_proposal()
    second = make_proposal(completion_claimed=True)
    agent = ScriptedAgent([first, second])

    proposal_one = await agent.propose_action(make_context())
    proposal_two = await agent.propose_action(make_context())

    assert proposal_one == first
    assert proposal_two == second
    assert proposal_one is not first
    assert proposal_two is not second


@pytest.mark.asyncio
async def test_scripted_agent_raises_when_exhausted() -> None:
    agent = ScriptedAgent([make_proposal()])

    await agent.propose_action(make_context())

    with pytest.raises(RuntimeError, match="no remaining proposals"):
        await agent.propose_action(make_context())


def test_agent_proposal_rejects_blank_strings() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        AgentProposal(
            summary="Valid summary",
            hypothesis="Valid hypothesis",
            evidence_considered=[""],
            files_to_inspect=[],
            edits=[],
            commands=[],
            expected_effect="Valid expected effect",
            risk_notes=[],
        )


@pytest.mark.asyncio
async def test_replay_agent_loads_jsonl_proposals(tmp_path) -> None:
    replay_path = tmp_path / "proposals.jsonl"
    payload = {"proposal": make_proposal(completion_claimed=True).model_dump(mode="json")}
    replay_path.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    agent = ReplayAgent(replay_path)
    proposal = await agent.propose_action(make_context())

    assert proposal.completion_claimed is True
    assert proposal.commands[0].argv[:2] == ["uv", "run"]
