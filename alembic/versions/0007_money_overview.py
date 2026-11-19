"""account types and balances, detailed category, budgets

Revision ID: 0007
Revises: 0006
"""

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("bank_accounts", sa.Column("type", sa.String, nullable=False, server_default=""))
    op.add_column("bank_accounts", sa.Column("subtype", sa.String, nullable=False, server_default=""))
    op.add_column("bank_accounts", sa.Column("balance_cents", sa.Integer))
    op.add_column("transactions", sa.Column("category_detail", sa.String))
    op.create_table(
        "budgets",
        sa.Column("category", sa.String, primary_key=True),
        sa.Column("limit_cents", sa.Integer, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )
    # replay every transaction on the next sync so old rows pick up their detailed category
    op.execute("UPDATE bank_items SET cursor = NULL")


def downgrade() -> None:
    op.drop_table("budgets")
    op.drop_column("transactions", "category_detail")
    op.drop_column("bank_accounts", "balance_cents")
    op.drop_column("bank_accounts", "subtype")
    op.drop_column("bank_accounts", "type")
