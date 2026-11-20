"""spec 13: homework agent sessions, steps and approvals

Revision ID: 0009
Revises: 0008
"""

import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_sessions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("task_id", sa.Integer, nullable=False),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("site", sa.String, nullable=False),
        sa.Column("status", sa.String, nullable=False),
        sa.Column("reason", sa.Text),
        sa.Column("started_at", sa.DateTime, nullable=False),
        sa.Column("ended_at", sa.DateTime),
        sa.Column("steps", sa.Integer, nullable=False, server_default="0"),
        sa.Column("input_tokens", sa.Integer, nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer, nullable=False, server_default="0"),
    )
    op.create_table(
        "agent_steps",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("session_id", sa.Integer, nullable=False, index=True),
        sa.Column("at", sa.DateTime, nullable=False),
        sa.Column("kind", sa.String, nullable=False),
        sa.Column("summary", sa.Text, nullable=False),
    )
    op.create_table(
        "approvals",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("session_id", sa.Integer, nullable=False, index=True),
        sa.Column("action_hash", sa.String, nullable=False),
        sa.Column("label", sa.Text, nullable=False),
        sa.Column("status", sa.String, nullable=False),
        sa.Column("expires_at", sa.DateTime, nullable=False),
        sa.Column("decided_at", sa.DateTime),
    )


def downgrade() -> None:
    op.drop_table("approvals")
    op.drop_table("agent_steps")
    op.drop_table("agent_sessions")
