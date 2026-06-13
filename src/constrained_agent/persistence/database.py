"""Async SQLAlchemy engine and session management."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from constrained_agent.persistence.models import Base
from constrained_agent.settings import Settings


class DatabaseEngine:
    """Own the async SQLAlchemy engine and session factory."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._engine: AsyncEngine | None = None
        self._session_factory: async_sessionmaker[AsyncSession] | None = None

    @property
    def engine(self) -> AsyncEngine:
        """Return the lazily initialized engine."""
        if self._engine is None:
            database_url = _normalize_database_url(self._settings.database_url)
            _ensure_database_parent(database_url)
            self._engine = create_async_engine(database_url, future=True)
            self._session_factory = async_sessionmaker(
                self._engine,
                expire_on_commit=False,
            )
        return self._engine

    def get_session(self) -> async_sessionmaker[AsyncSession]:
        """Return the configured async session factory."""
        _ = self.engine
        assert self._session_factory is not None
        return self._session_factory

    async def init_db(self) -> None:
        """Create all configured persistence tables."""
        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    async def dispose(self) -> None:
        """Dispose the underlying engine."""
        if self._engine is not None:
            await self._engine.dispose()
            self._engine = None
            self._session_factory = None


def _normalize_database_url(database_url: str) -> str:
    """Convert configured URLs into async-driver SQLAlchemy URLs."""
    url = make_url(database_url)
    if url.drivername == "sqlite":
        return str(url.set(drivername="sqlite+aiosqlite"))
    return database_url


def _ensure_database_parent(database_url: str) -> None:
    """Create parent directories for local SQLite databases."""
    url = make_url(database_url)
    if not url.drivername.startswith("sqlite"):
        return
    database = url.database
    if database in (None, "", ":memory:"):
        return
    Path(database).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
