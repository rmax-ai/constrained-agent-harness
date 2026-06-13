from __future__ import annotations

import os

import pytest

from constrained_agent.agents.google_adk import GoogleAdkCodingAgent
from constrained_agent.agents.protocol import AgentContext, AgentProposal
from constrained_agent.errors import ModelUnavailableError


def make_context() -> AgentContext:
    return AgentContext(
        goal_summary="Fix the failing test.",
        repository_map="src/ and tests/",
        candidate_diff="",
        evaluation_failures="tests/unit/test_example.py is failing",
        prior_rejected="",
        remaining_budget="2 iterations left",
        permitted_actions=["edit files", "run tests"],
        protected_summary="tests/protected is read-only",
        iteration=1,
    )


def valid_payload() -> dict[str, object]:
    return {
        "summary": "Inspect the failing module and update the implementation.",
        "hypothesis": "A missing guard clause is causing the failure.",
        "evidence_considered": ["failing unit test", "stack trace"],
        "files_to_inspect": ["src/constrained_agent/example.py"],
        "edits": [
            {
                "path": "src/constrained_agent/example.py",
                "operation": "patch",
                "unified_diff": (
                    "diff --git a/src/constrained_agent/example.py "
                    "b/src/constrained_agent/example.py\n"
                    "--- a/src/constrained_agent/example.py\n"
                    "+++ b/src/constrained_agent/example.py\n"
                    "@@ -1 +1 @@\n-old\n+new\n"
                ),
            }
        ],
        "commands": [
            {
                "argv": ["uv", "run", "pytest", "tests/unit/test_example.py"],
                "purpose": "verify the targeted regression",
                "timeout_seconds": 60,
            }
        ],
        "expected_effect": "The failing unit test should pass after the guard is added.",
        "risk_notes": ["The guard may need adjustment for edge cases."],
        "completion_claimed": False,
        "write_files": ["src/constrained_agent/example.py"],
        "diff": "",
    }


def test_credential_validation_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CAH_GOOGLE_API_KEY", "test-key")
    calls: list[str] = []

    def fake_validate(self: GoogleAdkCodingAgent) -> None:
        calls.append(self.get_model_info()["model_identifier"])  # type: ignore[arg-type]

    monkeypatch.setattr(GoogleAdkCodingAgent, "validate_credentials", fake_validate)

    agent = GoogleAdkCodingAgent(model_name="gemini-3.5-flash")

    assert calls == ["gemini-3.5-flash"]
    assert agent.get_model_info()["auth_mode"] == "google_ai_api"


def test_credential_validation_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CAH_GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("CAH_GOOGLE_CLOUD_PROJECT", raising=False)
    monkeypatch.delenv("CAH_GOOGLE_CLOUD_LOCATION", raising=False)
    monkeypatch.delenv("CAH_USE_VERTEX_AI", raising=False)

    with pytest.raises(ModelUnavailableError, match="Google AI API key not configured"):
        GoogleAdkCodingAgent()


@pytest.mark.asyncio
async def test_proposal_parsing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CAH_GOOGLE_API_KEY", "test-key")
    monkeypatch.setattr(GoogleAdkCodingAgent, "validate_credentials", lambda self: None)

    async def fake_request(self: GoogleAdkCodingAgent, prompt: str) -> dict[str, object]:
        assert "Goal summary" in prompt
        return valid_payload()

    monkeypatch.setattr(GoogleAdkCodingAgent, "_request_structured_response", fake_request)

    agent = GoogleAdkCodingAgent(model_name="gemini-3.5-flash")
    proposal = await agent.propose_action(make_context())

    assert isinstance(proposal, AgentProposal)
    assert proposal.commands[0].argv[:2] == ["uv", "run"]
    assert proposal.write_files == ["src/constrained_agent/example.py"]
    assert proposal.completion_claimed is False


@pytest.mark.asyncio
async def test_retry_on_validation_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CAH_GOOGLE_API_KEY", "test-key")
    monkeypatch.setattr(GoogleAdkCodingAgent, "validate_credentials", lambda self: None)
    prompts: list[str] = []
    responses = iter(
        [
            {"summary": "missing required fields"},
            valid_payload(),
        ]
    )

    async def fake_request(self: GoogleAdkCodingAgent, prompt: str) -> dict[str, object]:
        prompts.append(prompt)
        return next(responses)

    monkeypatch.setattr(GoogleAdkCodingAgent, "_request_structured_response", fake_request)

    agent = GoogleAdkCodingAgent(model_name="gemini-3.5-flash")
    proposal = await agent.propose_action(make_context())

    assert proposal.summary.startswith("Inspect the failing module")
    assert len(prompts) == 2
    assert "Validation feedback from the previous response" in prompts[1]


@pytest.mark.live_model
@pytest.mark.asyncio
async def test_live_model_proposal_round_trip() -> None:
    api_key = os.environ.get("CAH_GOOGLE_API_KEY")
    if not api_key:
        pytest.skip("CAH_GOOGLE_API_KEY is not configured")

    agent = GoogleAdkCodingAgent(model_name="gemini-3.5-flash", api_key=api_key)
    proposal = await agent.propose_action(make_context())

    assert isinstance(proposal, AgentProposal)
    assert proposal.completion_claimed is False
