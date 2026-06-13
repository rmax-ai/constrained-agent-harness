"""Completion manifest generation and verification."""

from __future__ import annotations

import json
import platform
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field

from constrained_agent.artifacts.store import ArtifactStore
from constrained_agent.domain.budgets import BudgetUsage
from constrained_agent.domain.candidates import Candidate
from constrained_agent.domain.events import Event, EventType, TransitionEvent
from constrained_agent.domain.evidence import ArtifactRef
from constrained_agent.domain.runs import Run


class CompletionManifest(BaseModel):
    """Structured completion manifest for a finalized run."""

    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(min_length=1)
    goal_contract_hash: str = Field(min_length=1)
    initial_repository_commit: str = Field(min_length=1)
    final_repository_commit: str = Field(min_length=1)
    model_provider: str = Field(min_length=1)
    model_identifier: str = Field(min_length=1)
    adk_version: str = Field(min_length=1)
    python_version: str = Field(min_length=1)
    container_image: str | None = None
    evaluator_versions: dict[str, str] = Field(default_factory=dict)
    final_evaluation_vector: dict[str, Any] = Field(default_factory=dict)
    hidden_check_result: str | None = None
    budget_usage: BudgetUsage
    event_chain_head_hash: str = Field(min_length=1)
    artifact_hashes: list[str] = Field(default_factory=list)
    completion_timestamp: datetime


class ManifestEventStore(Protocol):
    """Read-only event-store contract needed for manifest generation."""

    def list_events(self, run_id: str) -> list[Event]:
        """Return the ordered event chain for the run."""

    def list_artifacts(self, run_id: str) -> list[ArtifactRef]:
        """Return the stored artifacts for the run."""


def generate_manifest(
    run: Run,
    final_candidate: Candidate,
    artifact_store: ArtifactStore,
    event_store: ManifestEventStore,
) -> CompletionManifest:
    """Build a completion manifest and capture the event chain as an artifact."""
    model_metadata = run.metadata.get("model", {})
    events = event_store.list_events(str(run.id))
    artifacts = event_store.list_artifacts(str(run.id))
    event_chain_head_hash = events[-1].event_hash if events else ""
    chain_artifact = artifact_store.store(
        "event-chain.json",
        _serialize_event_chain(events),
        description="Canonical event chain snapshot",
    )
    artifact_hashes = [artifact.hash for artifact in artifacts]
    if chain_artifact.hash not in artifact_hashes:
        artifact_hashes.append(chain_artifact.hash)
    return CompletionManifest(
        run_id=str(run.id),
        goal_contract_hash=run.goal_hash,
        initial_repository_commit=run.initial_commit,
        final_repository_commit=final_candidate.repository_state_hash,
        model_provider=str(model_metadata.get("provider", "unknown")),
        model_identifier=str(
            model_metadata.get("model_identifier", model_metadata.get("name", "unknown"))
        ),
        adk_version=_package_version("google-adk"),
        python_version=platform.python_version(),
        container_image=_container_image_from_run(run),
        evaluator_versions=_evaluator_versions(run),
        final_evaluation_vector=_final_vector(final_candidate),
        hidden_check_result=_hidden_check_result(final_candidate),
        budget_usage=BudgetUsage.model_validate(run.metadata.get("budget_usage", {})),
        event_chain_head_hash=event_chain_head_hash,
        artifact_hashes=artifact_hashes,
        completion_timestamp=datetime.now(UTC),
    )


def verify_manifest(manifest: CompletionManifest, artifact_store: ArtifactStore) -> bool:
    """Verify stored artifacts and the serialized event-chain artifact."""
    for artifact_hash in manifest.artifact_hashes:
        ref = artifact_store.find_by_hash(artifact_hash)
        if ref is None or not artifact_store.verify(ref):
            return False

    chain_ref = _find_event_chain_artifact(manifest, artifact_store)
    if chain_ref is None:
        return False
    try:
        payload = json.loads(artifact_store.retrieve(chain_ref))
    except (OSError, ValueError):
        return False

    events: list[Event] = []
    for event_payload in payload.get("events", []):
        if event_payload.get("event_type") == EventType.STATE_TRANSITION.value:
            events.append(TransitionEvent.model_validate(event_payload))
        else:
            events.append(Event.model_validate(event_payload))
    previous_hash: str | None = None
    for event in events:
        if event.previous_event_hash != previous_hash:
            return False
        if Event.compute_hash(event, previous_hash) != event.event_hash:
            return False
        previous_hash = event.event_hash
    return previous_hash == manifest.event_chain_head_hash


def _serialize_event_chain(events: list[Event]) -> str:
    return json.dumps(
        {"events": [event.model_dump(mode="json") for event in events]},
        sort_keys=True,
        separators=(",", ":"),
    )


def _package_version(package_name: str) -> str:
    try:
        return version(package_name)
    except PackageNotFoundError:
        return "unavailable"


def _container_image_from_run(run: Run) -> str | None:
    container_image = run.metadata.get("container_image")
    if isinstance(container_image, str) and container_image != "":
        return container_image
    return None


def _evaluator_versions(run: Run) -> dict[str, str]:
    raw_versions = run.metadata.get("evaluator_versions", {})
    if isinstance(raw_versions, dict):
        return {str(key): str(value) for key, value in raw_versions.items()}
    return {}


def _final_vector(candidate: Candidate) -> dict[str, Any]:
    if candidate.evaluation is None:
        return {}
    return candidate.evaluation.model_dump(mode="json")


def _hidden_check_result(candidate: Candidate) -> str | None:
    if candidate.evaluation is None:
        return None
    hidden_failed = candidate.evaluation.hidden_tests_failed
    hidden_passed = candidate.evaluation.hidden_tests_passed
    if hidden_failed is None and hidden_passed is None:
        return "not_run"
    if hidden_failed and hidden_failed > 0:
        return "failed"
    return "passed"


def _find_event_chain_artifact(
    manifest: CompletionManifest,
    artifact_store: ArtifactStore,
) -> ArtifactRef | None:
    for artifact_hash in manifest.artifact_hashes:
        ref = artifact_store.find_by_hash(artifact_hash)
        if ref is None:
            continue
        suffixes = Path(ref.path).suffixes
        if suffixes[-2:] == [".event-chain", ".json"] or suffixes[-1:] == [".json"]:
            try:
                payload = json.loads(artifact_store.retrieve(ref))
            except (OSError, ValueError):
                continue
            if isinstance(payload, dict) and "events" in payload:
                return ref
    return None
