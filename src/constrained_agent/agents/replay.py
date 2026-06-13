"""Replay agent that reuses previously recorded proposal traces."""

from __future__ import annotations

import json
from pathlib import Path

from constrained_agent.agents.protocol import AgentContext, AgentProposal, CodingAgent


class ReplayAgent(CodingAgent):
    """Replay proposals recorded as JSONL entries."""

    def __init__(
        self,
        source: Path | str,
        *,
        model_info: dict[str, str | int | float | bool | None] | None = None,
    ) -> None:
        self._source = Path(source)
        self._proposals = self._load_proposals(self._source)
        self._index = 0
        self._model_info = model_info or {
            "provider": "replay",
            "model_identifier": str(self._source),
        }

    async def propose_action(self, context: AgentContext) -> AgentProposal:
        """Return the next recorded proposal."""
        del context
        if self._index >= len(self._proposals):
            raise RuntimeError("replay agent exhausted recorded proposals")
        proposal = self._proposals[self._index]
        self._index += 1
        return proposal.model_copy(deep=True)

    def get_model_info(self) -> dict[str, str | int | float | bool | None]:
        """Return metadata describing the replay source."""
        return dict(self._model_info)

    @staticmethod
    def _load_proposals(source: Path) -> list[AgentProposal]:
        proposals: list[AgentProposal] = []
        with source.open("r", encoding="utf-8") as handle:
            for line_number, raw_line in enumerate(handle, start=1):
                line = raw_line.strip()
                if line == "":
                    continue
                payload = json.loads(line)
                try:
                    proposal_payload = payload["proposal"]
                except KeyError:
                    proposal_payload = payload
                try:
                    proposals.append(AgentProposal.model_validate(proposal_payload))
                except Exception as exc:
                    raise ValueError(f"invalid proposal in {source} at line {line_number}") from exc
        if not proposals:
            raise ValueError(f"no proposals found in replay file: {source}")
        return proposals
