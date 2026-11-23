"""spec 15: message ids the gmail oa sweep already processed

Revision ID: 0011
Revises: 0010
"""

import sqlalchemy as sa

from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "gmail_seen",
        sa.Column("message_id", sa.String, primary_key=True),
        sa.Column("at", sa.DateTime, nullable=False),
    )


def downgrade() -> None:
    op.drop_table("gmail_seen")
