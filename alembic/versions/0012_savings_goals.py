"""spec 16: savings, investing and stretch goals for the money goals tab

Revision ID: 0012
Revises: 0011
"""

import sqlalchemy as sa
from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "savings_goals",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("kind", sa.String, nullable=False),
        sa.Column("account_id", sa.Integer, nullable=True),
        sa.Column("target_cents", sa.Integer, nullable=False),
        sa.Column("start", sa.Date, nullable=True),
        sa.Column("due", sa.Date, nullable=False),
        sa.Column("floor_cents", sa.Integer, nullable=True),
    )


def downgrade() -> None:
    op.drop_table("savings_goals")
