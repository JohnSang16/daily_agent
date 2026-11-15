"""outbound call audit table

Revision ID: 0002
Revises: 0001
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "outbound_calls",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, nullable=False),
        sa.Column("ts", sa.DateTime, nullable=False, index=True),
        sa.Column("integration", sa.String, nullable=False),
        sa.Column("method", sa.String, nullable=False),
        sa.Column("host", sa.String, nullable=False),
        sa.Column("path_template", sa.String, nullable=False),
        sa.Column("allowed", sa.Boolean, nullable=False),
        sa.Column("status", sa.Integer, nullable=True),
    )


def downgrade() -> None:
    op.drop_table("outbound_calls")
