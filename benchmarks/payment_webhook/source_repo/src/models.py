from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class PaymentWebhookEvent(BaseModel):
    event_id: str = Field(min_length=1)
    amount: float
    currency: str = Field(min_length=1)
    event_type: str = "payment.created"


class PaymentResponse(BaseModel):
    id: int
    event_id: str
    amount: float
    currency: str
    created_at: datetime
