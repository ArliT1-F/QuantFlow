"""Initial migration

Revision ID: 0001
Revises:
Create Date: 11-02-2026
"""

from alembic import op
import sqlalchemy as sa


revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ---------------------------
    # Portfolios
    # ---------------------------
    op.create_table(
        "portfolios",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("total_value", sa.Float(), nullable=False),
        sa.Column("cash_balance", sa.Float(), nullable=False),
        sa.Column("invested_amount", sa.Float(), nullable=False),
        sa.Column("total_pnl", sa.Float(), nullable=True),
        sa.Column("total_pnl_percentage", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_portfolios_id"), "portfolios", ["id"], unique=False)

    # ---------------------------
    # Portfolio Snapshots
    # ---------------------------
    op.create_table(
        "portfolio_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("portfolio_id", sa.Integer(), nullable=False),
        sa.Column("total_value", sa.Float(), nullable=False),
        sa.Column("cash_balance", sa.Float(), nullable=False),
        sa.Column("invested_amount", sa.Float(), nullable=False),
        sa.Column("total_pnl", sa.Float(), nullable=True),
        sa.Column("total_pnl_percentage", sa.Float(), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True),
                  server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("daily_return", sa.Float(), nullable=True),
        sa.Column("weekly_return", sa.Float(), nullable=True),
        sa.Column("monthly_return", sa.Float(), nullable=True),
        sa.Column("sharpe_ratio", sa.Float(), nullable=True),
        sa.Column("max_drawdown", sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_portfolio_snapshots_id"),
                    "portfolio_snapshots", ["id"], unique=False)

    # ---------------------------
    # Trades
    # ---------------------------
    op.create_table(
        "trades",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("symbol", sa.String(length=10), nullable=False),
        sa.Column("side", sa.String(length=4), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("price", sa.Float(), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True),
                  server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("strategy", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=True),
        sa.Column("order_type", sa.String(length=20), nullable=True),
        sa.Column("stop_loss", sa.Float(), nullable=True),
        sa.Column("take_profit", sa.Float(), nullable=True),
        sa.Column("fees", sa.Float(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("portfolio_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["portfolio_id"], ["portfolios.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_trades_id"), "trades", ["id"], unique=False)
    op.create_index(op.f("ix_trades_symbol"),
                    "trades", ["symbol"], unique=False)

    # ---------------------------
    # Positions
    # ---------------------------
    op.create_table(
        "positions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("symbol", sa.String(length=10), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("average_price", sa.Float(), nullable=False),
        sa.Column("current_price", sa.Float(), nullable=False),
        sa.Column("unrealized_pnl", sa.Float(), nullable=True),
        sa.Column("realized_pnl", sa.Float(), nullable=True),
        sa.Column("stop_loss", sa.Float(), nullable=True),
        sa.Column("take_profit", sa.Float(), nullable=True),
        sa.Column("opened_at", sa.DateTime(timezone=True),
                  server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("portfolio_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["portfolio_id"], ["portfolios.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_positions_id"), "positions", ["id"], unique=False)
    op.create_index(op.f("ix_positions_symbol"),
                    "positions", ["symbol"], unique=False)

    # ---------------------------
    # Strategies
    # ---------------------------
    op.create_table(
        "strategies",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("strategy_type", sa.String(length=50), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("parameters", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_strategies_id"),
                    "strategies", ["id"], unique=False)
    op.create_index(op.f("ix_strategies_name"),
                    "strategies", ["name"], unique=True)

    # ---------------------------
    # Runtime Settings
    # ---------------------------
    op.create_table(
        "runtime_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("value", sa.String(length=255), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_runtime_settings_id"),
                    "runtime_settings", ["id"], unique=False)
    op.create_index(op.f("ix_runtime_settings_key"),
                    "runtime_settings", ["key"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_runtime_settings_key"),
                  table_name="runtime_settings")
    op.drop_index(op.f("ix_runtime_settings_id"),
                  table_name="runtime_settings")
    op.drop_table("runtime_settings")

    op.drop_index(op.f("ix_strategies_name"), table_name="strategies")
    op.drop_index(op.f("ix_strategies_id"), table_name="strategies")
    op.drop_table("strategies")

    op.drop_index(op.f("ix_positions_symbol"), table_name="positions")
    op.drop_index(op.f("ix_positions_id"), table_name="positions")
    op.drop_table("positions")

    op.drop_index(op.f("ix_trades_symbol"), table_name="trades")
    op.drop_index(op.f("ix_trades_id"), table_name="trades")
    op.drop_table("trades")

    op.drop_index(op.f("ix_portfolio_snapshots_id"),
                  table_name="portfolio_snapshots")
    op.drop_table("portfolio_snapshots")

    op.drop_index(op.f("ix_portfolios_id"), table_name="portfolios")
    op.drop_table("portfolios")
