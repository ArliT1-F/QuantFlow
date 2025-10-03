"""Initial migration

Revision ID: 0001
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create portfolios table
    op.create_table('portfolios',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('total_value', sa.Float(), nullable=False),
        sa.Column('cash_balance', sa.Float(), nullable=False),
        sa.Column('invested_amount', sa.Float(), nullable=False),
        sa.Column('total_pnl', sa.Float(), nullable=True),
        sa.Column('total_pnl_percentage', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_portfolios_id'), 'portfolios', ['id'], unique=False)

    # Create portfolio_snapshots table
    op.create_table('portfolio_snapshots',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('portfolio_id', sa.Integer(), nullable=False),
        sa.Column('total_value', sa.Float(), nullable=False),
        sa.Column('cash_balance', sa.Float(), nullable=False),
        sa.Column('invested_amount', sa.Float(), nullable=False),
        sa.Column('total_pnl', sa.Float(), nullable=True),
        sa.Column('total_pnl_percentage', sa.Float(), nullable=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('daily_return', sa.Float(), nullable=True),
        sa.Column('weekly_return', sa.Float(), nullable=True),
        sa.Column('monthly_return', sa.Float(), nullable=True),
        sa.Column('sharpe_ratio', sa.Float(), nullable=True),
        sa.Column('max_drawdown', sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_portfolio_snapshots_id'), 'portfolio_snapshots', ['id'], unique=False)

    # Create trades table
    op.create_table('trades',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('symbol', sa.String(length=10), nullable=False),
        sa.Column('side', sa.String(length=4), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('price', sa.Float(), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('strategy', sa.String(length=50), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=True),
        sa.Column('order_type', sa.String(length=20), nullable=True),
        sa.Column('stop_loss', sa.Float(), nullable=True),
        sa.Column('take_profit', sa.Float(), nullable=True),
        sa.Column('fees', sa.Float(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('portfolio_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['portfolio_id'], ['portfolios.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_trades_id'), 'trades', ['id'], unique=False)
    op.create_index(op.f('ix_trades_symbol'), 'trades', ['symbol'], unique=False)

    # Create positions table
    op.create_table('positions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('symbol', sa.String(length=10), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('average_price', sa.Float(), nullable=False),
        sa.Column('current_price', sa.Float(), nullable=False),
        sa.Column('unrealized_pnl', sa.Float(), nullable=True),
        sa.Column('realized_pnl', sa.Float(), nullable=True),
        sa.Column('stop_loss', sa.Float(), nullable=True),
        sa.Column('take_profit', sa.Float(), nullable=True),
        sa.Column('opened_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('portfolio_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['portfolio_id'], ['portfolios.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_positions_id'), 'positions', ['id'], unique=False)
    op.create_index(op.f('ix_positions_symbol'), 'positions', ['symbol'], unique=False)

    # Create strategies table
    op.create_table('strategies',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('strategy_type', sa.String(length=50), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('parameters', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('total_trades', sa.Integer(), nullable=True),
        sa.Column('winning_trades', sa.Integer(), nullable=True),
        sa.Column('losing_trades', sa.Integer(), nullable=True),
        sa.Column('win_rate', sa.Float(), nullable=True),
        sa.Column('total_pnl', sa.Float(), nullable=True),
        sa.Column('sharpe_ratio', sa.Float(), nullable=True),
        sa.Column('max_drawdown', sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_strategies_id'), 'strategies', ['id'], unique=False)
    op.create_index(op.f('ix_strategies_name'), 'strategies', ['name'], unique=True)

    # Create strategy_signals table
    op.create_table('strategy_signals',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('strategy_id', sa.Integer(), nullable=False),
        sa.Column('symbol', sa.String(length=10), nullable=False),
        sa.Column('signal_type', sa.String(length=10), nullable=False),
        sa.Column('strength', sa.Float(), nullable=False),
        sa.Column('price', sa.Float(), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_strategy_signals_id'), 'strategy_signals', ['id'], unique=False)
    op.create_index(op.f('ix_strategy_signals_symbol'), 'strategy_signals', ['symbol'], unique=False)

    # Create alerts table
    op.create_table('alerts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('alert_type', sa.String(length=50), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('symbol', sa.String(length=10), nullable=True),
        sa.Column('price', sa.Float(), nullable=True),
        sa.Column('threshold', sa.Float(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=True),
        sa.Column('priority', sa.String(length=10), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_alerts_id'), 'alerts', ['id'], unique=False)
    op.create_index(op.f('ix_alerts_symbol'), 'alerts', ['symbol'], unique=False)

    # Create alert_rules table
    op.create_table('alert_rules',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('alert_type', sa.String(length=50), nullable=False),
        sa.Column('symbol', sa.String(length=10), nullable=True),
        sa.Column('condition', sa.String(length=100), nullable=False),
        sa.Column('threshold', sa.Float(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_alert_rules_id'), 'alert_rules', ['id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_alert_rules_id'), table_name='alert_rules')
    op.drop_table('alert_rules')
    op.drop_index(op.f('ix_alerts_symbol'), table_name='alerts')
    op.drop_index(op.f('ix_alerts_id'), table_name='alerts')
    op.drop_table('alerts')
    op.drop_index(op.f('ix_strategy_signals_symbol'), table_name='strategy_signals')
    op.drop_index(op.f('ix_strategy_signals_id'), table_name='strategy_signals')
    op.drop_table('strategy_signals')
    op.drop_index(op.f('ix_strategies_name'), table_name='strategies')
    op.drop_index(op.f('ix_strategies_id'), table_name='strategies')
    op.drop_table('strategies')
    op.drop_index(op.f('ix_positions_symbol'), table_name='positions')
    op.drop_index(op.f('ix_positions_id'), table_name='positions')
    op.drop_table('positions')
    op.drop_index(op.f('ix_trades_symbol'), table_name='trades')
    op.drop_index(op.f('ix_trades_id'), table_name='trades')
    op.drop_table('trades')
    op.drop_index(op.f('ix_portfolio_snapshots_id'), table_name='portfolio_snapshots')
    op.drop_table('portfolio_snapshots')
    op.drop_index(op.f('ix_portfolios_id'), table_name='portfolios')
    op.drop_table('portfolios')