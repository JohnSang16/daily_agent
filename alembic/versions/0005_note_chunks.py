"""note_chunks for asking the vault

Revision ID: 0005
Revises: 0004
"""

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "note_chunks",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("path", sa.String, nullable=False, index=True),
        sa.Column("chunk_index", sa.Integer, nullable=False),
        sa.Column("heading", sa.String, nullable=False),
        sa.Column("content_hash", sa.String, nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
        sa.UniqueConstraint("path", "chunk_index"),
    )


def downgrade() -> None:
    op.drop_table("note_chunks")
