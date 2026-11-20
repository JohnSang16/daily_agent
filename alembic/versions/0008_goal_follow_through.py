"""spec 18: daily check-in, input and outcome goals

Revision ID: 0008
Revises: 0007
"""

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "daily_checkin",
        sa.Column("day", sa.String, primary_key=True),
        sa.Column("obstacle", sa.Text),
        sa.Column("if_then", sa.Text),
        sa.Column("top_task_title", sa.Text),
        sa.Column("did_top", sa.Boolean),
        sa.Column("why_not", sa.Text),
        sa.Column("let_go", sa.Text),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )
    op.create_table(
        "goals",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("kind", sa.String, nullable=False),
        sa.Column("unit", sa.String, nullable=False, server_default=""),
        sa.Column("target", sa.Integer, nullable=False),
        sa.Column("current", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("archived", sa.Boolean, nullable=False, server_default=sa.false()),
    )
    op.create_table(
        "goal_logs",
        sa.Column("goal_id", sa.Integer, primary_key=True),
        sa.Column("day", sa.String, primary_key=True),
        sa.Column("count", sa.Integer, nullable=False),
    )


def downgrade() -> None:
    op.drop_table("goal_logs")
    op.drop_table("goals")
    op.drop_table("daily_checkin")
