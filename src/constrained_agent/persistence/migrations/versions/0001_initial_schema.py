"""initial schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-06-13
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "runs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("goal_hash", sa.String(length=64), nullable=False),
        sa.Column("initial_commit", sa.String(length=64), nullable=False),
        sa.Column("experiment_mode", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "events",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("iteration", sa.Integer(), nullable=False),
        sa.Column("source_state", sa.String(length=64), nullable=True),
        sa.Column("target_state", sa.String(length=64), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("event_hash", sa.String(length=64), nullable=False),
        sa.Column("previous_event_hash", sa.String(length=64), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"]),
    )
    op.create_index("ix_events_run_id", "events", ["run_id"])
    op.create_index("ix_events_event_hash", "events", ["event_hash"], unique=True)
    op.create_table(
        "candidates",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("repository_state_hash", sa.String(length=64), nullable=False),
        sa.Column("parent_id", sa.String(length=36), nullable=True),
        sa.Column("depth", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("iteration", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["parent_id"], ["candidates.id"]),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"]),
    )
    op.create_index("ix_candidates_run_id", "candidates", ["run_id"])
    op.create_index("ix_candidates_repository_state_hash", "candidates", ["repository_state_hash"])
    op.create_table(
        "evaluations",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("candidate_id", sa.String(length=36), nullable=False),
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("vector", sa.JSON(), nullable=False),
        sa.Column("tier", sa.String(length=32), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.id"]),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"]),
    )
    op.create_index("ix_evaluations_candidate_id", "evaluations", ["candidate_id"])
    op.create_index("ix_evaluations_run_id", "evaluations", ["run_id"])
    op.create_table(
        "artifacts",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("hash", sa.String(length=64), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"]),
    )
    op.create_index("ix_artifacts_run_id", "artifacts", ["run_id"])
    op.create_index("ix_artifacts_hash", "artifacts", ["hash"])


def downgrade() -> None:
    op.drop_index("ix_artifacts_hash", table_name="artifacts")
    op.drop_index("ix_artifacts_run_id", table_name="artifacts")
    op.drop_table("artifacts")
    op.drop_index("ix_evaluations_run_id", table_name="evaluations")
    op.drop_index("ix_evaluations_candidate_id", table_name="evaluations")
    op.drop_table("evaluations")
    op.drop_index("ix_candidates_repository_state_hash", table_name="candidates")
    op.drop_index("ix_candidates_run_id", table_name="candidates")
    op.drop_table("candidates")
    op.drop_index("ix_events_event_hash", table_name="events")
    op.drop_index("ix_events_run_id", table_name="events")
    op.drop_table("events")
    op.drop_table("runs")
