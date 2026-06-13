"""SQLAlchemy ORM models for persistent run state."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base declarative class for persistence models."""


class RunModel(Base):
    """Persistent run record."""

    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    goal_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    initial_commit: Mapped[str] = mapped_column(String(64), nullable=False)
    experiment_mode: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    events: Mapped[list[EventModel]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )
    candidates: Mapped[list[CandidateModel]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
    )
    evaluations: Mapped[list[EvaluationModel]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
    )
    artifacts: Mapped[list[ArtifactModel]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
    )


class EventModel(Base):
    """Persistent append-only event."""

    __tablename__ = "events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    iteration: Mapped[int] = mapped_column(Integer, nullable=False)
    source_state: Mapped[str | None] = mapped_column(String(64))
    target_state: Mapped[str | None] = mapped_column(String(64))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    event_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    previous_event_hash: Mapped[str | None] = mapped_column(String(64))
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    run: Mapped[RunModel] = relationship(back_populates="events")


class CandidateModel(Base):
    """Persistent candidate record."""

    __tablename__ = "candidates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), nullable=False, index=True)
    repository_state_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    parent_id: Mapped[str | None] = mapped_column(ForeignKey("candidates.id"))
    depth: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    iteration: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    run: Mapped[RunModel] = relationship(back_populates="candidates")
    parent: Mapped[CandidateModel | None] = relationship(remote_side="CandidateModel.id")
    evaluations: Mapped[list[EvaluationModel]] = relationship(
        back_populates="candidate",
        cascade="all, delete-orphan",
    )


class EvaluationModel(Base):
    """Persistent evaluation vector."""

    __tablename__ = "evaluations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    candidate_id: Mapped[str] = mapped_column(
        ForeignKey("candidates.id"), nullable=False, index=True
    )
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), nullable=False, index=True)
    vector: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    tier: Mapped[str] = mapped_column(String(32), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    candidate: Mapped[CandidateModel] = relationship(back_populates="evaluations")
    run: Mapped[RunModel] = relationship(back_populates="evaluations")


class ArtifactModel(Base):
    """Persistent artifact metadata."""

    __tablename__ = "artifacts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), nullable=False, index=True)
    path: Mapped[str] = mapped_column(Text, nullable=False)
    hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    run: Mapped[RunModel] = relationship(back_populates="artifacts")
