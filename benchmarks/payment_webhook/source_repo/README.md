# Payment Webhook

Small FastAPI application that records incoming payment webhook events in
SQLite.

Known issue: duplicate deliveries with the same `event_id` currently create
multiple payment rows.
