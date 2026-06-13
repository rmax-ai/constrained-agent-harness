"""Google ADK adapter for structured Gemini coding proposals."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from google import genai
from google.adk import Agent, Runner
from google.adk.models import Gemini
from google.adk.sessions import InMemorySessionService
from google.genai import types as genai_types
from pydantic import ValidationError

from constrained_agent.agents.prompts import (
    CODING_AGENT_SYSTEM_PROMPT,
    render_coding_agent_prompt,
)
from constrained_agent.agents.protocol import AgentContext, AgentProposal, CodingAgent
from constrained_agent.errors import ModelUnavailableError
from constrained_agent.settings import Settings

_REQUIRED_PROPOSAL_FIELDS = frozenset(
    {
        "summary",
        "hypothesis",
        "evidence_considered",
        "files_to_inspect",
        "edits",
        "commands",
        "expected_effect",
        "risk_notes",
        "completion_claimed",
        "write_files",
        "diff",
    }
)


@dataclass(frozen=True)
class _ResolvedGoogleAuth:
    """Resolved authentication configuration for Gemini access."""

    mode: str
    api_key: str | None = None
    project: str | None = None
    location: str | None = None

    def client_kwargs(self) -> dict[str, Any]:
        if self.mode == "vertex_ai":
            return {
                "vertexai": True,
                "project": self.project,
                "location": self.location,
            }
        return {"api_key": self.api_key}


class _ConfiguredGeminiModel(Gemini):
    """Gemini model wrapper with explicit client configuration."""

    auth_config: _ResolvedGoogleAuth

    @property
    def api_client(self) -> genai.Client:
        base_url, api_version = self._base_url_and_api_version
        http_options_kwargs: dict[str, Any] = {
            "headers": self._tracking_headers(),
            "retry_options": self.retry_options,
            "base_url": base_url,
        }
        if api_version:
            http_options_kwargs["api_version"] = api_version
        return genai.Client(
            **self.auth_config.client_kwargs(),
            http_options=genai_types.HttpOptions(**http_options_kwargs),
        )


class GoogleAdkCodingAgent(CodingAgent):
    """Coding-agent adapter backed by Google ADK structured Gemini responses."""

    _APP_NAME = "constrained-agent-harness"
    _OUTPUT_KEY = "proposal"
    _MAX_RETRIES = 3

    def __init__(
        self,
        *,
        model_name: str | None = None,
        temperature: float = 0.0,
        api_key: str | None = None,
        vertex_project: str | None = None,
        vertex_location: str | None = None,
        use_vertex_ai: bool | None = None,
        goal_model: str | None = None,
        max_validation_retries: int = _MAX_RETRIES,
    ) -> None:
        settings = Settings()
        self._model_name = settings.resolve_model(goal_model=goal_model, cli_model=model_name)
        self._temperature = temperature
        self._max_validation_retries = max_validation_retries
        self._auth = self._resolve_auth(
            api_key=api_key,
            vertex_project=vertex_project,
            vertex_location=vertex_location,
            use_vertex_ai=use_vertex_ai,
            settings=settings,
        )
        self.validate_credentials()

    async def propose_action(self, context: AgentContext) -> AgentProposal:
        """Request a structured proposal with validation-aware retries."""
        feedback: str | None = None
        attempts = self._max_validation_retries + 1
        for attempt in range(1, attempts + 1):
            prompt = render_coding_agent_prompt(context, validation_feedback=feedback)
            try:
                raw_response = await self._request_structured_response(prompt)
                proposal = self._coerce_proposal(raw_response)
            except (ValidationError, ValueError) as exc:
                if attempt >= attempts:
                    raise ValueError(
                        f"agent proposal validation failed after {attempts} attempts"
                    ) from exc
                feedback = self._format_validation_feedback(exc)
                continue

            if proposal.completion_claimed:
                proposal = proposal.model_copy(update={"completion_claimed": False})
            if not proposal.write_files and proposal.edits:
                proposal = proposal.model_copy(
                    update={"write_files": [edit.path for edit in proposal.edits]}
                )
            return proposal

        raise AssertionError("unreachable")

    def validate_credentials(self) -> None:
        """Fail fast if the configured model cannot be reached."""
        try:
            self._run_validation_probe()
        except ModelUnavailableError:
            raise
        except Exception as exc:  # pragma: no cover - defensive wrapper around SDK errors
            raise ModelUnavailableError(
                f"unable to reach model {self._model_name!r} with auth mode {self._auth.mode}"
            ) from exc

    def get_model_info(self) -> dict[str, str | int | float | bool | None]:
        """Return resolved model and auth metadata for auditing."""
        return {
            "provider": "google-adk",
            "model_identifier": self._model_name,
            "temperature": self._temperature,
            "auth_mode": self._auth.mode,
            "vertex_project": self._auth.project,
            "vertex_location": self._auth.location,
        }

    @staticmethod
    def _resolve_auth(
        *,
        api_key: str | None,
        vertex_project: str | None,
        vertex_location: str | None,
        use_vertex_ai: bool | None,
        settings: Settings,
    ) -> _ResolvedGoogleAuth:
        resolved_use_vertex = settings.use_vertex_ai if use_vertex_ai is None else use_vertex_ai
        if resolved_use_vertex:
            project = (
                vertex_project
                or settings.google_cloud_project
                or os.environ.get("CAH_GOOGLE_CLOUD_PROJECT")
            )
            location = (
                vertex_location
                or settings.google_cloud_location
                or os.environ.get("CAH_GOOGLE_CLOUD_LOCATION")
            )
            if not project or not location:
                raise ModelUnavailableError(
                    "Vertex AI requires CAH_GOOGLE_CLOUD_PROJECT and CAH_GOOGLE_CLOUD_LOCATION"
                )
            return _ResolvedGoogleAuth(
                mode="vertex_ai",
                project=project,
                location=location,
            )

        resolved_api_key = (
            api_key or settings.google_api_key or os.environ.get("CAH_GOOGLE_API_KEY")
        )
        if not resolved_api_key:
            raise ModelUnavailableError(
                "Google AI API key not configured; set CAH_GOOGLE_API_KEY or enable Vertex AI"
            )
        return _ResolvedGoogleAuth(mode="google_ai_api", api_key=resolved_api_key)

    def _build_genai_client(self) -> genai.Client:
        return genai.Client(**self._auth.client_kwargs())

    def _build_adk_model(self) -> Gemini:
        return _ConfiguredGeminiModel(
            model=self._model_name,
            auth_config=self._auth,
        )

    def _build_adk_agent(self) -> Agent:
        return Agent(
            name="cah_coding_agent",
            model=self._build_adk_model(),
            instruction=CODING_AGENT_SYSTEM_PROMPT,
            output_schema=AgentProposal,
            output_key=self._OUTPUT_KEY,
            include_contents="none",
            mode="chat",
            generate_content_config=genai_types.GenerateContentConfig(
                temperature=self._temperature,
            ),
        )

    def _run_validation_probe(self) -> None:
        client = self._build_genai_client()
        client.models.generate_content(
            model=self._model_name,
            contents="Return OK.",
            config=genai_types.GenerateContentConfig(
                temperature=0.0,
                max_output_tokens=8,
            ),
        )

    async def _request_structured_response(self, prompt: str) -> Any:
        session_service = InMemorySessionService()
        runner = Runner(
            app_name=self._APP_NAME,
            agent=self._build_adk_agent(),
            session_service=session_service,
        )
        user_id = "cah"
        session = await session_service.create_session(
            app_name=self._APP_NAME,
            user_id=user_id,
            session_id=str(uuid4()),
        )
        message = genai_types.Content(
            role="user",
            parts=[genai_types.Part(text=prompt)],
        )
        async for _ in runner.run_async(
            user_id=session.user_id,
            session_id=session.id,
            new_message=message,
        ):
            pass
        updated_session = await session_service.get_session(
            app_name=self._APP_NAME,
            user_id=session.user_id,
            session_id=session.id,
        )
        if updated_session is None:
            raise ValueError("ADK session disappeared before structured output could be read")
        if self._OUTPUT_KEY not in updated_session.state:
            raise ValueError("ADK response did not populate the structured proposal output")
        return updated_session.state[self._OUTPUT_KEY]

    @staticmethod
    def _format_validation_feedback(exc: Exception) -> str:
        return (
            "The previous response did not match the AgentProposal schema. "
            f"Return a corrected structured object. Validation error: {exc}"
        )

    @staticmethod
    def _coerce_proposal(raw_response: Any) -> AgentProposal:
        if isinstance(raw_response, AgentProposal):
            return raw_response.model_copy(deep=True)
        if isinstance(raw_response, dict):
            missing_fields = sorted(_REQUIRED_PROPOSAL_FIELDS.difference(raw_response))
            if missing_fields:
                raise ValueError(
                    "structured proposal omitted required fields: " + ", ".join(missing_fields)
                )
        return AgentProposal.model_validate(raw_response)
