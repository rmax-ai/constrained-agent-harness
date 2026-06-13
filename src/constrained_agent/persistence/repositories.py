"""Repository classes for persistence models."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from constrained_agent.persistence.models import (
    ArtifactModel,
    CandidateModel,
    EventModel,
    RunModel,
)


class RunRepository:
    """CRUD access for runs."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def create(self, **values: object) -> RunModel:
        async with self._session_factory() as session:
            model = RunModel(**values)
            session.add(model)
            await session.commit()
            await session.refresh(model)
            return model

    async def get(self, run_id: str) -> RunModel | None:
        async with self._session_factory() as session:
            return await session.get(RunModel, run_id)

    async def update(self, run_id: str, **values: object) -> RunModel | None:
        async with self._session_factory() as session:
            model = await session.get(RunModel, run_id)
            if model is None:
                return None
            for key, value in values.items():
                setattr(model, key, value)
            await session.commit()
            await session.refresh(model)
            return model

    async def list(self) -> Sequence[RunModel]:
        async with self._session_factory() as session:
            result = await session.scalars(select(RunModel).order_by(RunModel.created_at))
            return result.all()


class EventRepository:
    """Append-only event persistence."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def create(self, **values: object) -> EventModel:
        async with self._session_factory() as session:
            model = EventModel(**values)
            session.add(model)
            await session.commit()
            await session.refresh(model)
            return model

    async def get_by_run(self, run_id: str) -> Sequence[EventModel]:
        async with self._session_factory() as session:
            query: Select[tuple[EventModel]] = select(EventModel).where(EventModel.run_id == run_id)
            result = await session.scalars(
                query.order_by(EventModel.iteration, EventModel.timestamp)
            )
            return result.all()

    async def get_chain(self, run_id: str) -> Sequence[EventModel]:
        async with self._session_factory() as session:
            query: Select[tuple[EventModel]] = select(EventModel).where(EventModel.run_id == run_id)
            result = await session.scalars(
                query.order_by(EventModel.iteration, EventModel.timestamp)
            )
            return result.all()


class CandidateRepository:
    """Persistence for candidate repository states."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def create(self, **values: object) -> CandidateModel:
        async with self._session_factory() as session:
            model = CandidateModel(**values)
            session.add(model)
            await session.commit()
            await session.refresh(model)
            return model

    async def get(self, candidate_id: str) -> CandidateModel | None:
        async with self._session_factory() as session:
            return await session.get(CandidateModel, candidate_id)

    async def list_by_run(self, run_id: str) -> Sequence[CandidateModel]:
        async with self._session_factory() as session:
            query: Select[tuple[CandidateModel]] = select(CandidateModel).where(
                CandidateModel.run_id == run_id
            )
            result = await session.scalars(
                query.order_by(CandidateModel.iteration, CandidateModel.depth)
            )
            return result.all()

    async def update_status(self, candidate_id: str, status: str) -> CandidateModel | None:
        async with self._session_factory() as session:
            model = await session.get(CandidateModel, candidate_id)
            if model is None:
                return None
            model.status = status
            await session.commit()
            await session.refresh(model)
            return model


class ArtifactRepository:
    """Persistence for artifact metadata."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def create(self, **values: object) -> ArtifactModel:
        async with self._session_factory() as session:
            model = ArtifactModel(**values)
            session.add(model)
            await session.commit()
            await session.refresh(model)
            return model

    async def list_by_run(self, run_id: str) -> Sequence[ArtifactModel]:
        async with self._session_factory() as session:
            query: Select[tuple[ArtifactModel]] = select(ArtifactModel).where(
                ArtifactModel.run_id == run_id
            )
            result = await session.scalars(query.order_by(ArtifactModel.timestamp))
            return result.all()
