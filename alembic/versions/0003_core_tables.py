"""tasks, events, sync_runs, oauth_tokens, llm_usage, explanation_cache

Revision ID: 0003
Revises: 0002
"""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

pk = lambda: sa.Column("id", sa.Integer, primary_key=True)  # noqa: E731


def upgrade() -> None:
    op.create_table(
        "tasks", pk(),
        sa.Column("user_id", sa.Integer, nullable=False),
        sa.Column("source", sa.String, nullable=False),
        sa.Column("scope", sa.String, nullable=False),
        sa.Column("source_ref", sa.String, nullable=False),
        sa.Column("fingerprint", sa.String, nullable=False),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("due_at", sa.DateTime),
        sa.Column("due_is_date_only", sa.Boolean, nullable=False),
        sa.Column("effort_minutes", sa.Integer),
        sa.Column("importance", sa.Integer),
        sa.Column("status", sa.String, nullable=False),
        sa.Column("snoozed_until", sa.DateTime),
        sa.Column("needs_review", sa.Boolean, nullable=False),
        sa.Column("review_reason", sa.Text),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
        sa.Column("last_seen_at", sa.DateTime, nullable=False),
        sa.UniqueConstraint("user_id", "source", "fingerprint"),
    )
    op.create_table(
        "events", pk(),
        sa.Column("user_id", sa.Integer, nullable=False),
        sa.Column("source", sa.String, nullable=False),
        sa.Column("source_ref", sa.String, nullable=False),
        sa.Column("calendar_id", sa.String, nullable=False),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("start_at", sa.DateTime, nullable=False),
        sa.Column("end_at", sa.DateTime, nullable=False),
        sa.Column("all_day", sa.Boolean, nullable=False),
        sa.Column("busy", sa.Boolean, nullable=False),
        sa.Column("status", sa.String, nullable=False),
        sa.Column("location", sa.Text),
        sa.Column("updated_at", sa.DateTime, nullable=False),
        sa.Column("last_seen_at", sa.DateTime, nullable=False),
        sa.UniqueConstraint("user_id", "source", "calendar_id", "source_ref", "start_at"),
    )
    op.create_table(
        "sync_runs", pk(),
        sa.Column("source", sa.String, nullable=False),
        sa.Column("started_at", sa.DateTime, nullable=False),
        sa.Column("finished_at", sa.DateTime),
        sa.Column("status", sa.String, nullable=False),
        sa.Column("items_seen", sa.Integer, nullable=False),
        sa.Column("items_changed", sa.Integer, nullable=False),
        sa.Column("error_summary", sa.Text),
        sa.Column("duration_ms", sa.Integer),
    )
    op.create_table(
        "oauth_tokens", pk(),
        sa.Column("user_id", sa.Integer, nullable=False),
        sa.Column("provider", sa.String, nullable=False),
        sa.Column("encrypted_blob", sa.Text, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )
    op.create_table(
        "llm_usage", pk(),
        sa.Column("at", sa.DateTime, nullable=False),
        sa.Column("purpose", sa.String, nullable=False),
        sa.Column("model", sa.String, nullable=False),
        sa.Column("input_tokens", sa.Integer, nullable=False),
        sa.Column("output_tokens", sa.Integer, nullable=False),
    )
    op.create_table(
        "explanation_cache",
        sa.Column("key", sa.String, primary_key=True),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )


def downgrade() -> None:
    for t in ("explanation_cache", "llm_usage", "oauth_tokens", "sync_runs", "events", "tasks"):
        op.drop_table(t)
