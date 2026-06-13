from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.app import create_app


def _make_client(tmp_path: Path) -> TestClient:
    os.environ["PAYMENT_DB_PATH"] = str(tmp_path / "payments.db")
    return TestClient(create_app())


def _fetch_payments(db_path: Path) -> list[tuple[int, str, float, str]]:
    with sqlite3.connect(db_path) as connection:
        rows = connection.execute(
            "SELECT id, event_id, amount, currency FROM payments ORDER BY id ASC"
        ).fetchall()
    return [(int(row[0]), str(row[1]), float(row[2]), str(row[3])) for row in rows]


def test_valid_webhook_creates_payment(tmp_path: Path) -> None:
    db_path = tmp_path / "payments.db"
    with _make_client(tmp_path) as client:
        response = client.post(
            "/webhook",
            json={"event_id": "evt_100", "amount": 19.99, "currency": "USD"},
        )

    assert response.status_code == 200
    assert _fetch_payments(db_path) == [(1, "evt_100", 19.99, "USD")]


def test_malformed_payload_rejected(tmp_path: Path) -> None:
    with _make_client(tmp_path) as client:
        response = client.post(
            "/webhook",
            content="{bad json",
            headers={"content-type": "application/json"},
        )

    assert response.status_code == 422


def test_duplicate_sequential_delivery(tmp_path: Path) -> None:
    db_path = tmp_path / "payments.db"
    with _make_client(tmp_path) as client:
        first = client.post(
            "/webhook",
            json={"event_id": "evt_dup", "amount": 42.0, "currency": "USD"},
        )
        second = client.post(
            "/webhook",
            json={"event_id": "evt_dup", "amount": 42.0, "currency": "USD"},
        )

    assert first.status_code == 200
    assert second.status_code == 200
    payments = _fetch_payments(db_path)
    assert len(payments) == 1
    assert payments[0][1:] == ("evt_dup", 42.0, "USD")
    assert second.json()["id"] == first.json()["id"]


def test_webhook_returns_payment_data(tmp_path: Path) -> None:
    with _make_client(tmp_path) as client:
        response = client.post(
            "/webhook",
            json={"event_id": "evt_body", "amount": 10.5, "currency": "EUR"},
        )

    assert response.status_code == 200
    assert response.json()["event_id"] == "evt_body"
    assert response.json()["amount"] == 10.5
    assert response.json()["currency"] == "EUR"
    assert "created_at" in response.json()
