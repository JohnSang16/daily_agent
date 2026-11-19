"""bank_items, bank_accounts, transactions

Revision ID: 0006
Revises: 0005
"""

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "bank_items",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, nullable=False),
        sa.Column("plaid_item_id", sa.String, nullable=False),
        sa.Column("institution_id", sa.String, nullable=False),
        sa.Column("institution_name", sa.String, nullable=False),
        sa.Column("access_token_enc", sa.Text, nullable=False),
        sa.Column("cursor", sa.String),
        sa.Column("last_sync_at", sa.DateTime),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )
    op.create_table(
        "bank_accounts",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("item_id", sa.Integer, nullable=False, index=True),
        sa.Column("account_id", sa.String, nullable=False),
        sa.Column("nickname", sa.String, nullable=False),
        sa.Column("mask", sa.String, nullable=False),
        sa.Column("enabled", sa.Boolean, nullable=False),
        sa.UniqueConstraint("item_id", "account_id"),
    )
    op.create_table(
        "transactions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("account_id", sa.Integer, nullable=False, index=True),
        sa.Column("source_id", sa.String, nullable=False, unique=True),
        sa.Column("posted_date", sa.Date, nullable=False),
        sa.Column("merchant", sa.Text, nullable=False),
        sa.Column("amount_cents", sa.Integer, nullable=False),
        sa.Column("direction", sa.String, nullable=False),
        sa.Column("category", sa.String),
        sa.Column("pending", sa.Boolean, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_transactions_date_id", "transactions", ["posted_date", "id"])


def downgrade() -> None:
    op.drop_table("transactions")
    op.drop_table("bank_accounts")
    op.drop_table("bank_items")
