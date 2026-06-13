from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, Response, status

from src.database import Database, Payment
from src.models import PaymentResponse, PaymentWebhookEvent


def _to_response(payment: Payment) -> PaymentResponse:
    return PaymentResponse(
        id=payment.id,
        event_id=payment.event_id,
        amount=payment.amount,
        currency=payment.currency,
        created_at=payment.created_at,
    )


def create_app() -> FastAPI:
    database = Database()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.db = database
        await database.init_models()
        yield
        await database.dispose()

    app = FastAPI(title="Payment Webhook", lifespan=lifespan)

    @app.post("/webhook", response_model=PaymentResponse)
    async def receive_webhook(event: PaymentWebhookEvent, response: Response):
        if event.event_type != "payment.created":
            response.status_code = status.HTTP_202_ACCEPTED
            return PaymentResponse(
                id=0,
                event_id=event.event_id,
                amount=event.amount,
                currency=event.currency,
                created_at=datetime.now(timezone.utc),
            )

        payment = await database.create_payment(
            event_id=event.event_id,
            amount=event.amount,
            currency=event.currency,
        )
        return _to_response(payment)

    return app


app = create_app()
