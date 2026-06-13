from __future__ import annotations

import asyncio
import os
import sqlite3
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

for candidate_root in (
    Path.cwd(),
    Path(__file__).resolve().parents[1],
    Path(__file__).resolve().parents[1] / "source_repo",
    Path(__file__).resolve().parents[1] / "reference_solution",
):
    if (candidate_root / "src" / "app.py").is_file():
        sys.path.insert(0, str(candidate_root))
        break

from src.app import create_app
from src.database import Database


def _db_path(tmp_path: Path) -> Path:
    return tmp_path / "payments.db"


def _make_client(tmp_path: Path) -> TestClient:
    os.environ["PAYMENT_DB_PATH"] = str(_db_path(tmp_path))
    return TestClient(create_app())


def _row_count(db_path: Path, event_id: str) -> int:
    with sqlite3.connect(db_path) as connection:
        count = connection.execute(
            "SELECT COUNT(*) FROM payments WHERE event_id = ?",
            (event_id,),
        ).fetchone()
    assert count is not None
    return int(count[0])


def test_concurrent_duplicate_delivery(tmp_path: Path) -> None:
    payload = {"event_id": "evt_race", "amount": 9.0, "currency": "USD"}

    def _send() -> int:
        with _make_client(tmp_path) as client:
            response = client.post("/webhook", json=payload)
            return response.status_code

    async def _exercise() -> list[int]:
        return await asyncio.gather(asyncio.to_thread(_send), asyncio.to_thread(_send))

    statuses = asyncio.run(_exercise())
    assert statuses == [200, 200]
    assert _row_count(_db_path(tmp_path), "evt_race") == 1


def test_transaction_rollback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    os.environ["PAYMENT_DB_PATH"] = str(_db_path(tmp_path))
    database = Database()
    asyncio.run(database.init_models())

    original_factory = database.session_factory

    def failing_factory():
        session = original_factory()
        original_commit = session.commit

        async def failing_commit() -> None:
            await session.rollback()
            raise RuntimeError("simulated commit failure")

        session.commit = failing_commit  # type: ignore[method-assign]
        session._original_commit = original_commit  # type: ignore[attr-defined]
        return session

    monkeypatch.setattr(database, "session_factory", failing_factory)

    async def _attempt_insert() -> None:
        if hasattr(database, "create_or_get_payment"):
            await database.create_or_get_payment(  # type: ignore[attr-defined]
                event_id="evt_fail",
                amount=1.0,
                currency="USD",
            )
            return
        await database.create_payment(event_id="evt_fail", amount=1.0, currency="USD")  # type: ignore[attr-defined]

    with pytest.raises(RuntimeError, match="simulated commit failure"):
        asyncio.run(_attempt_insert())

    assert _row_count(_db_path(tmp_path), "evt_fail") == 0
    asyncio.run(database.dispose())


def test_idempotency_key_persistence(tmp_path: Path) -> None:
    payload = {"event_id": "evt_restart", "amount": 7.5, "currency": "USD"}

    with _make_client(tmp_path) as client:
        first = client.post("/webhook", json=payload)

    with _make_client(tmp_path) as client:
        second = client.post("/webhook", json=payload)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    assert _row_count(_db_path(tmp_path), "evt_restart") == 1


def test_unexpected_event_types(tmp_path: Path) -> None:
    with _make_client(tmp_path) as client:
        response = client.post(
            "/webhook",
            json={
                "event_id": "evt_ignore",
                "amount": 4.0,
                "currency": "USD",
                "event_type": "invoice.created",
            },
        )

    assert response.status_code == 202
    assert _row_count(_db_path(tmp_path), "evt_ignore") == 0


def test_no_hardcoded_fixtures(tmp_path: Path) -> None:
    dynamic_event_id = f"evt_dynamic_{tmp_path.name}"

    with _make_client(tmp_path) as client:
        first = client.post(
            "/webhook",
            json={"event_id": dynamic_event_id, "amount": 3.25, "currency": "USD"},
        )
        second = client.post(
            "/webhook",
            json={"event_id": dynamic_event_id, "amount": 3.25, "currency": "USD"},
        )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    assert _row_count(_db_path(tmp_path), dynamic_event_id) == 1
