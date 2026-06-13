from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from sqlalchemy import DateTime, Float, Integer, String, UniqueConstraint, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _default_database_url() -> str:
    db_path = Path(os.environ.get("PAYMENT_DB_PATH", "payments.db"))
    return f"sqlite+aiosqlite:///{db_path}"


class Base(DeclarativeBase):
    pass


class Payment(Base):
    __tablename__ = "payments"
    __table_args__ = (UniqueConstraint("event_id", name="uq_payments_event_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String, nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


class Database:
    def __init__(self, database_url: str | None = None) -> None:
        self.database_url = database_url or _default_database_url()
        self.engine = create_async_engine(self.database_url, future=True)
        self.session_factory = async_sessionmaker(
            self.engine,
            expire_on_commit=False,
            class_=AsyncSession,
        )

    async def init_models(self) -> None:
        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    async def dispose(self) -> None:
        await self.engine.dispose()

    async def create_or_get_payment(
        self,
        *,
        event_id: str,
        amount: float,
        currency: str,
    ) -> tuple[Payment, bool]:
        async with self.session_factory() as session:
            payment = Payment(event_id=event_id, amount=amount, currency=currency)
            session.add(payment)
            try:
                await session.commit()
                await session.refresh(payment)
                return payment, True
            except IntegrityError:
                await session.rollback()

            existing = await self._get_payment_by_event_id(session, event_id)
            if existing is None:
                raise RuntimeError(f"payment for event_id {event_id!r} disappeared after rollback")
            return existing, False

    async def _get_payment_by_event_id(
        self,
        session: AsyncSession,
        event_id: str,
    ) -> Payment | None:
        statement = select(Payment).where(Payment.event_id == event_id)
        result = await session.execute(statement)
        return result.scalars().first()
