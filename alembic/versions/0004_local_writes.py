"""daily_goal table and tasks.locally_done

Revision ID: 0004
Revises: 0003
"""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "daily_goal",
        sa.Column("day", sa.String, primary_key=True),
        sa.Column("text", sa.String, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )
    op.add_column(
        "tasks", sa.Column("locally_done", sa.Boolean, nullable=False, server_default=sa.false())
    )


def downgrade() -> None:
    op.drop_column("tasks", "locally_done")
    op.drop_table("daily_goal")
