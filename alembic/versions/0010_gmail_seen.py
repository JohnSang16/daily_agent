"""spec 15: message ids the gmail oa sweep already processed

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
        "gmail_seen",
        sa.Column("message_id", sa.String, primary_key=True),
        sa.Column("at", sa.DateTime, nullable=False),
    )


def downgrade() -> None:
    op.drop_table("gmail_seen")
