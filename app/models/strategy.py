"""
Strategy model for trading strategy configuration
"""
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Text, JSON
from sqlalchemy.sql import func
from app.core.database import Base

class Strategy(Base):
    """Trading strategy model"""
    __tablename__ = "strategies"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    strategy_type = Column(String(50), nullable=False)  # momentum, mean_reversion, etc.
    is_active = Column(Boolean, default=True)
    parameters = Column(JSON, nullable=True)  # Strategy-specific parameters
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Performance metrics
    total_trades = Column(Integer, default=0)
    winning_trades = Column(Integer, default=0)
    losing_trades = Column(Integer, default=0)
    win_rate = Column(Float, default=0.0)
    total_pnl = Column(Float, default=0.0)
    sharpe_ratio = Column(Float, default=0.0)
    max_drawdown = Column(Float, default=0.0)

class StrategySignal(Base):
    """Strategy signal model for tracking buy/sell signals"""
    __tablename__ = "strategy_signals"
    
    id = Column(Integer, primary_key=True, index=True)
    strategy_id = Column(Integer, nullable=False)
    symbol = Column(String(10), nullable=False, index=True)
    signal_type = Column(String(10), nullable=False)  # BUY, SELL, HOLD
    strength = Column(Float, nullable=False)  # Signal strength 0-1
    price = Column(Float, nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    signal_metadata = Column(JSON, nullable=True)  # Additional signal data
