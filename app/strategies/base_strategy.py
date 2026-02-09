"""
Base strategy class that all trading strategies inherit from
"""
from abc import ABC, abstractmethod
from typing import Dict, Optional, Any
import pandas as pd
import numpy as np
from dataclasses import dataclass
from app.core.config import settings

@dataclass
class Signal:
    """Trading signal data structure"""
    symbol: str
    action: str  # BUY, SELL, HOLD
    confidence: float  # 0-1
    price: float
    quantity: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    metadata: Dict[str, Any] = None

class BaseStrategy(ABC):
    """Abstract base class for all trading strategies"""
    
    def __init__(self, name: str = ""):
        self.name = name or self.__class__.__name__
        self.parameters = {}
        self.performance_metrics = {
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "win_rate": 0.0,
            "total_pnl": 0.0,
            "sharpe_ratio": 0.0,
            "max_drawdown": 0.0
        }
    
    @abstractmethod
    async def generate_signal(self, symbol: str, data: Dict[str, Any]) -> Optional[Signal]:
        """
        Generate a trading signal for the given symbol and data
        
        Args:
            symbol: Coin symbol
            data: Market data for the symbol
            
        Returns:
            Signal object or None if no signal
        """
        pass
    
    def calculate_position_size(self, signal: Signal, portfolio_value: float, risk_per_trade: float = 0.02) -> int:
        """
        Calculate position size based on risk management
        
        Args:
            signal: Trading signal
            portfolio_value: Total portfolio value
            risk_per_trade: Risk per trade as percentage of portfolio
            
        Returns:
            Number of shares to trade
        """
        if signal.stop_loss is None:
            return 0
        
        risk_amount = portfolio_value * risk_per_trade
        price_risk = abs(signal.price - signal.stop_loss)
        
        if price_risk <= 0:
            return 0
        
        position_size = int(risk_amount / price_risk)
        return max(1, position_size)  # Minimum 1 share
    
    def calculate_stop_loss(self, price: float, action: str, stop_loss_pct: Optional[float] = None) -> float:
        """
        Calculate stop loss price
        
        Args:
            price: Entry price
            action: BUY or SELL
            stop_loss_pct: Stop loss percentage
            
        Returns:
            Stop loss price
        """
        stop_loss_pct = settings.STOP_LOSS_PERCENTAGE if stop_loss_pct is None else stop_loss_pct

        if action == "BUY":
            return price * (1 - stop_loss_pct)
        else:  # SELL
            return price * (1 + stop_loss_pct)
    
    def calculate_take_profit(self, price: float, action: str, take_profit_pct: Optional[float] = None) -> float:
        """
        Calculate take profit price
        
        Args:
            price: Entry price
            action: BUY or SELL
            take_profit_pct: Take profit percentage
            
        Returns:
            Take profit price
        """
        take_profit_pct = settings.TAKE_PROFIT_PERCENTAGE if take_profit_pct is None else take_profit_pct

        if action == "BUY":
            return price * (1 + take_profit_pct)
        else:  # SELL
            return price * (1 - take_profit_pct)
    
    def update_performance(self, trade_result: Dict[str, Any]):
        """
        Update strategy performance metrics
        
        Args:
            trade_result: Result of a completed trade
        """
        self.performance_metrics["total_trades"] += 1
        
        pnl = trade_result.get("pnl", 0)
        self.performance_metrics["total_pnl"] += pnl
        
        if pnl > 0:
            self.performance_metrics["winning_trades"] += 1
        else:
            self.performance_metrics["losing_trades"] += 1
        
        # Update win rate
        total = self.performance_metrics["total_trades"]
        if total > 0:
            self.performance_metrics["win_rate"] = (
                self.performance_metrics["winning_trades"] / total
            )
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get current performance metrics"""
        return self.performance_metrics.copy()
    
    def validate_data(self, data: Dict[str, Any]) -> bool:
        """
        Validate that data contains required fields
        
        Args:
            data: Market data dictionary
            
        Returns:
            True if data is valid, False otherwise
        """
        required_fields = ["price", "volume", "timestamp"]
        return all(field in data for field in required_fields)
    
    def calculate_technical_indicators(self, data: Dict[str, Any]) -> Dict[str, float]:
        """
        Calculate basic technical indicators from data
        
        Args:
            data: Market data dictionary
            
        Returns:
            Dictionary of technical indicators
        """
        indicators = {}
        
        # Price-based indicators
        price = data.get("price", 0)
        high = data.get("high", price)
        low = data.get("low", price)
        open_price = data.get("open", price)
        
        # Price change
        indicators["price_change"] = price - open_price
        indicators["price_change_pct"] = (price - open_price) / open_price * 100 if open_price > 0 else 0
        
        # High-Low range
        indicators["hl_range"] = high - low
        indicators["hl_range_pct"] = (high - low) / low * 100 if low > 0 else 0
        
        # Volume indicators
        volume = data.get("volume", 0)
        indicators["volume"] = volume
        
        return indicators
