"""eod log: the nightly bullets that get written into the vault

Revision ID: 0010
Revises: 0009
"""

import sqlalchemy as sa
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "eod_entries",
        sa.Column("day", sa.String, primary_key=True),
        sa.Column("bullets", sa.Text, nullable=False),
        sa.Column("logged_at", sa.DateTime, nullable=False),
    )


def downgrade() -> None:
    op.drop_table("eod_entries")
