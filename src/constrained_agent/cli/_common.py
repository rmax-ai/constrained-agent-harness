"""Shared CLI runtime helpers."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from alembic import command
from alembic.config import Config
from sqlalchemy import select
from sqlalchemy.engine import make_url

from constrained_agent.artifacts import CompletionManifest
from constrained_agent.persistence import (
    ArtifactRepository,
    CandidateRepository,
    DatabaseEngine,
    EventRepository,
    RunRepository,
)
from constrained_agent.persistence.models import (
    ArtifactModel,
    CandidateModel,
    EvaluationModel,
)
from constrained_agent.settings import Settings


class LoadedRunData(dict[str, Any]):
    """Typed dict-like carrier for CLI inspection helpers."""


def run_async(coro: Any) -> Any:
    """Run an async coroutine from synchronous Typer commands."""
    return asyncio.run(coro)


async def load_run_data(settings: Settings, run_id: str) -> LoadedRunData:
    """Load a run and its related persisted records."""
    engine = DatabaseEngine(settings)
    try:
        run_repo = RunRepository(engine.get_session())
        event_repo = EventRepository(engine.get_session())
        candidate_repo = CandidateRepository(engine.get_session())
        artifact_repo = ArtifactRepository(engine.get_session())

        run = await run_repo.get(run_id)
        if run is None:
            raise ValueError(f"run not found: {run_id}")
        events = list(await event_repo.get_by_run(run_id))
        candidates = list(await candidate_repo.list_by_run(run_id))
        artifacts = list(await artifact_repo.list_by_run(run_id))
        evaluations = await _load_evaluations(engine, run_id)
        manifest, manifest_ref = _load_manifest(artifacts)
        return LoadedRunData(
            run=run,
            events=events,
            candidates=candidates,
            artifacts=artifacts,
            evaluations=evaluations,
            manifest=manifest,
            manifest_ref=manifest_ref,
        )
    finally:
        await engine.dispose()


async def load_candidate(settings: Settings, candidate_id: str) -> CandidateModel | None:
    """Load a single candidate by id."""
    engine = DatabaseEngine(settings)
    try:
        repo = CandidateRepository(engine.get_session())
        return await repo.get(candidate_id)
    finally:
        await engine.dispose()


async def init_database(settings: Settings) -> None:
    """Create the configured database if needed."""
    engine = DatabaseEngine(settings)
    try:
        await engine.init_db()
    finally:
        await engine.dispose()


def upgrade_database(settings: Settings) -> None:
    """Run Alembic migrations for the configured database."""
    url = make_url(settings.database_url)
    if url.drivername.startswith("sqlite") and url.database not in (None, "", ":memory:"):
        Path(url.database).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
    config = Config(str(Path(__file__).resolve().parents[3] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", settings.database_url)
    command.upgrade(config, "head")


async def _load_evaluations(engine: DatabaseEngine, run_id: str) -> list[EvaluationModel]:
    session_factory = engine.get_session()
    async with session_factory() as session:
        result = await session.scalars(
            select(EvaluationModel)
            .where(EvaluationModel.run_id == run_id)
            .order_by(EvaluationModel.timestamp)
        )
        return list(result.all())


def _load_manifest(
    artifacts: list[ArtifactModel],
) -> tuple[CompletionManifest | None, str | None]:
    for artifact in reversed(artifacts):
        path = Path(artifact.path)
        if ".completion-manifest." not in path.name:
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            return CompletionManifest.model_validate(payload), artifact.hash
        except (OSError, ValueError):
            continue
    return None, None
