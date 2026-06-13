from __future__ import annotations

import os

import pytest

from constrained_agent.agents.google_adk import GoogleAdkCodingAgent
from constrained_agent.agents.protocol import AgentContext, AgentProposal


def _api_key() -> str | None:
    return os.environ.get("CAH_GOOGLE_API_KEY")


def _make_context() -> AgentContext:
    return AgentContext(
        goal_summary="Return a safe structured proposal for a small code fix.",
        repository_map="src/constrained_agent/example.py\ntests/unit/test_example.py",
        candidate_diff="",
        evaluation_failures="tests/unit/test_example.py is failing",
        prior_rejected="none",
        remaining_budget="2 iterations remaining",
        permitted_actions=["edit files under src/**", "run allowed commands: uv, python, git"],
        protected_summary="tests/**",
        iteration=1,
    )


pytestmark = [pytest.mark.live_model, pytest.mark.asyncio]


def _skip_if_unconfigured() -> str:
    api_key = _api_key()
    if not api_key:
        pytest.skip("CAH_GOOGLE_API_KEY is not configured")
    return api_key


async def test_credential_validation() -> None:
    api_key = _skip_if_unconfigured()

    agent = GoogleAdkCodingAgent(model_name="gemini-3.5-flash", api_key=api_key)

    agent.validate_credentials()


async def test_model_accessibility() -> None:
    api_key = _skip_if_unconfigured()
    agent = GoogleAdkCodingAgent(model_name="gemini-3.5-flash", api_key=api_key)

    agent.validate_credentials()

    assert agent.get_model_info()["provider"] == "google-adk"


async def test_structured_output() -> None:
    api_key = _skip_if_unconfigured()
    agent = GoogleAdkCodingAgent(model_name="gemini-3.5-flash", api_key=api_key)

    proposal = await agent.propose_action(_make_context())

    assert isinstance(proposal, AgentProposal)
    assert proposal.summary.strip() != ""
    assert proposal.completion_claimed is False


async def test_retry_on_invalid(monkeypatch: pytest.MonkeyPatch) -> None:
    api_key = _skip_if_unconfigured()
    original_request = GoogleAdkCodingAgent._request_structured_response
    calls = 0

    async def flaky_request(
        self: GoogleAdkCodingAgent,
        prompt: str,
    ) -> object:
        nonlocal calls
        calls += 1
        if calls == 1:
            return {"summary": "missing required fields"}
        return await original_request(self, prompt)

    monkeypatch.setattr(GoogleAdkCodingAgent, "_request_structured_response", flaky_request)
    agent = GoogleAdkCodingAgent(model_name="gemini-3.5-flash", api_key=api_key)

    proposal = await agent.propose_action(_make_context())

    assert isinstance(proposal, AgentProposal)
    assert calls == 2
