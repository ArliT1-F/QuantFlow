"""Add trade execution metadata columns

Revision ID: 0002
Revises: 0001
Create Date: 2026-02-18
"""

from alembic import op
import sqlalchemy as sa


revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("trades", sa.Column("execution_mode", sa.String(length=16), nullable=True))
    op.add_column("trades", sa.Column("tx_signature", sa.String(length=128), nullable=True))
    op.add_column("trades", sa.Column("request_id", sa.String(length=64), nullable=True))
    op.add_column("trades", sa.Column("chain_id", sa.String(length=32), nullable=True))
    op.add_column("trades", sa.Column("base_token_address", sa.String(length=64), nullable=True))
    op.add_column("trades", sa.Column("quote_token_address", sa.String(length=64), nullable=True))
    op.add_column("trades", sa.Column("pair_address", sa.String(length=128), nullable=True))


def downgrade() -> None:
    op.drop_column("trades", "pair_address")
    op.drop_column("trades", "quote_token_address")
    op.drop_column("trades", "base_token_address")
    op.drop_column("trades", "chain_id")
    op.drop_column("trades", "request_id")
    op.drop_column("trades", "tx_signature")
    op.drop_column("trades", "execution_mode")
