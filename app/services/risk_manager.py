"""
Risk management system for controlling trading risk
"""
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import numpy as np
from dataclasses import dataclass

from app.core.config import settings
from app.strategies.base_strategy import Signal

logger = logging.getLogger(__name__)

@dataclass
class RiskLimits:
    """Risk limit configuration"""
    max_position_size: float = 0.1  # 10% of portfolio
    max_portfolio_risk: float = 0.02  # 2% portfolio risk per trade
    max_daily_loss: float = 0.05  # 5% max daily loss
    max_drawdown: float = 0.15  # 15% max drawdown
    max_correlation: float = 0.7  # Max correlation between positions
    max_sector_exposure: float = 0.3  # 30% max exposure to any sector
    max_daily_trades: int = 10
    min_volume: int = 100000

class RiskManager:
    """Risk management system for controlling trading risk"""
    
    def __init__(self, portfolio_manager: Optional[Any] = None):
        self.risk_limits = RiskLimits()
        self.daily_trades = 0
        self.daily_pnl = 0.0
        self.last_reset_date = datetime.utcnow().date()
        self.position_correlations = {}
        self.sector_exposures = {}
        self.portfolio_manager = portfolio_manager

        # Sync limits from settings
        self.risk_limits.max_position_size = settings.MAX_POSITION_SIZE
        self.risk_limits.max_portfolio_risk = settings.MAX_PORTFOLIO_RISK
        self.risk_limits.max_daily_trades = settings.MAX_DAILY_TRADES
        self.risk_limits.min_volume = settings.MIN_VOLUME
        
        logger.info("Risk manager initialized")
    
    async def validate_signal(self, signal: Signal) -> (bool, str):
        """
        Validate if a trading signal meets risk criteria
        
        Args:
            signal: Trading signal to validate
            
        Returns:
            True if signal is valid, False otherwise
        """
        try:
            # Check daily trade limit
            if not self._check_daily_trade_limit():
                return False, "daily trade limit reached"
            
            # Check daily loss limit
            if not self._check_daily_loss_limit():
                return False, "daily loss limit reached"

            # Apply position sizing (clamps to limits)
            sized_qty = await self.calculate_position_size(signal)
            if sized_qty <= 0:
                return False, "position size too small"
            signal.quantity = sized_qty
            
            # Check correlation limits
            if not await self._check_correlation_limit(signal):
                return False, "correlation limit exceeded"
            
            # Check sector exposure limits
            if not await self._check_sector_exposure_limit(signal):
                return False, "sector exposure limit exceeded"
            
            # Check volume requirements
            if not self._check_volume_requirements(signal):
                return False, "volume too low"
            
            return True, ""
            
        except Exception as e:
            logger.error(f"Error validating signal for {signal.symbol}: {e}")
            return False, "validation error"
    
    def _check_daily_trade_limit(self) -> bool:
        """Check if daily trade limit is exceeded"""
        self._reset_daily_counters_if_needed()
        return self.daily_trades < self.risk_limits.max_daily_trades
    
    def _check_daily_loss_limit(self) -> bool:
        """Check if daily loss limit is exceeded"""
        self._reset_daily_counters_if_needed()
        portfolio_value = self._get_portfolio_value()
        max_daily_loss_amount = portfolio_value * self.risk_limits.max_daily_loss
        return self.daily_pnl > -max_daily_loss_amount
    
    async def _check_position_size_limit(self, signal: Signal) -> bool:
        """Check if position size is within limits"""
        try:
            portfolio_value = self._get_portfolio_value()
            if portfolio_value <= 0:
                return False
            position_size = await self.calculate_position_size(signal)
            position_value = signal.price * position_size
            position_size_ratio = position_value / portfolio_value
            
            return position_size_ratio <= self.risk_limits.max_position_size
            
        except Exception as e:
            logger.error(f"Error checking position size limit: {e}")
            return False
    
    async def _check_portfolio_risk_limit(self, signal: Signal) -> bool:
        """Check if portfolio risk limit is exceeded"""
        try:
            # Calculate risk per trade
            if signal.stop_loss is None:
                return False
            
            risk_per_share = abs(signal.price - signal.stop_loss)
            position_size = await self.calculate_position_size(signal)
            total_risk = risk_per_share * position_size
            
            portfolio_value = self._get_portfolio_value()
            if portfolio_value <= 0:
                return False
            risk_ratio = total_risk / portfolio_value
            
            return risk_ratio <= self.risk_limits.max_portfolio_risk
            
        except Exception as e:
            logger.error(f"Error checking portfolio risk limit: {e}")
            return False
    
    async def _check_correlation_limit(self, signal: Signal) -> bool:
        """Check if correlation limit is exceeded"""
        try:
            # This would typically calculate correlation with existing positions
            # For now, we'll use a simplified check
            symbol = signal.symbol
            
            if symbol in self.position_correlations:
                max_correlation = max(self.position_correlations[symbol].values())
                return max_correlation <= self.risk_limits.max_correlation
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking correlation limit: {e}")
            return True
    
    async def _check_sector_exposure_limit(self, signal: Signal) -> bool:
        """Check if sector exposure limit is exceeded"""
        try:
            # This would typically check against actual sector data
            # For now, we'll use a simplified check
            symbol = signal.symbol
            
            # Simulate sector exposure
            current_exposure = self.sector_exposures.get(symbol, 0.05)  # 5% default
            
            return current_exposure <= self.risk_limits.max_sector_exposure
            
        except Exception as e:
            logger.error(f"Error checking sector exposure limit: {e}")
            return True
    
    def _check_volume_requirements(self, signal: Signal) -> bool:
        """Check if volume requirements are met"""
        volume = None
        if signal.metadata:
            volume = signal.metadata.get("volume")
        if volume is None:
            return True
        return volume >= self.risk_limits.min_volume
    
    async def calculate_position_size(self, signal: Signal) -> float:
        """
        Calculate optimal position size based on risk management
        
        Args:
            signal: Trading signal
            
        Returns:
            Number of shares to trade
        """
        try:
            portfolio_value = self._get_portfolio_value()
            if portfolio_value <= 0:
                return 0
            
            # Calculate position size based on risk per trade
            if signal.stop_loss is None:
                return 0
            
            risk_per_share = abs(signal.price - signal.stop_loss)
            if risk_per_share <= 0:
                return 0
            max_risk_amount = portfolio_value * self.risk_limits.max_portfolio_risk
            
            # Calculate position size
            position_size = max_risk_amount / risk_per_share
            
            # Apply position size limit
            max_position_value = portfolio_value * self.risk_limits.max_position_size
            max_units_by_value = max_position_value / signal.price if signal.price > 0 else 0.0
            
            # Use the smaller of the two limits
            final_position_size = min(position_size, max_units_by_value)
            
            # Ensure minimum tradable size/notional
            if final_position_size <= 0:
                return 0.0
            # Cap by max units but also enforce minimum units and notional
            final_position_size = max(final_position_size, settings.MIN_POSITION_UNITS)
            if signal.price > 0 and final_position_size * signal.price < settings.MIN_POSITION_NOTIONAL:
                final_position_size = settings.MIN_POSITION_NOTIONAL / signal.price
            return float(final_position_size)
            
        except Exception as e:
            logger.error(f"Error calculating position size: {e}")
            return 0
    
    def _reset_daily_counters_if_needed(self):
        """Reset daily counters if it's a new day"""
        current_date = datetime.utcnow().date()
        
        if current_date != self.last_reset_date:
            self.daily_trades = 0
            self.daily_pnl = 0.0
            self.last_reset_date = current_date
            logger.info("Daily risk counters reset")
    
    async def record_trade(self, trade_data: Dict[str, Any]):
        """
        Record a trade for risk tracking
        
        Args:
            trade_data: Trade data to record
        """
        try:
            self.daily_trades += 1
            
            # Update daily P&L
            pnl = trade_data.get("pnl", 0)
            self.daily_pnl += pnl
            
            # Update position correlations (simplified)
            symbol = trade_data.get("symbol", "")
            if symbol:
                self.position_correlations[symbol] = {
                    "BTC-USD": 0.3,  # Simulated correlation
                    "ETH-USD": 0.4,
                    "SOL-USD": 0.2
                }
            
            # Update sector exposures (simplified)
            self.sector_exposures[symbol] = 0.05  # 5% default
            
            logger.info(f"Trade recorded: {symbol}, Daily trades: {self.daily_trades}, Daily P&L: {self.daily_pnl}")
            
        except Exception as e:
            logger.error(f"Error recording trade: {e}")
    
    async def check_risk_limits(self):
        """Check all risk limits and take action if necessary"""
        try:
            # Check daily loss limit
            if self.daily_pnl < -self.risk_limits.max_daily_loss:
                logger.warning(f"Daily loss limit exceeded: {self.daily_pnl}")
                # In a real implementation, this would trigger risk management actions
                # such as closing positions, stopping trading, etc.
            
            # Check drawdown limit
            # This would typically check against portfolio peak value
            current_drawdown = 0.05  # Simulated 5% drawdown
            if current_drawdown > self.risk_limits.max_drawdown:
                logger.warning(f"Maximum drawdown exceeded: {current_drawdown}")
                # Trigger risk management actions
            
            logger.info("Risk limits check completed")
            
        except Exception as e:
            logger.error(f"Error checking risk limits: {e}")
    
    def get_risk_metrics(self) -> Dict[str, Any]:
        """Get current risk metrics"""
        self._reset_daily_counters_if_needed()
        
        return {
            "daily_trades": self.daily_trades,
            "daily_pnl": self.daily_pnl,
            "max_daily_trades": self.risk_limits.max_daily_trades,
            "max_daily_loss": self.risk_limits.max_daily_loss,
            "max_position_size": self.risk_limits.max_position_size,
            "max_portfolio_risk": self.risk_limits.max_portfolio_risk,
            "position_correlations": self.position_correlations,
            "sector_exposures": self.sector_exposures,
            "last_reset_date": self.last_reset_date.isoformat()
        }

    def _get_portfolio_value(self) -> float:
        """Get current portfolio value for risk calculations"""
        if self.portfolio_manager:
            return max(self.portfolio_manager.total_value, 0.0)
        return settings.DEFAULT_CAPITAL
    
    def update_risk_limits(self, new_limits: Dict[str, Any]):
        """
        Update risk limits
        
        Args:
            new_limits: Dictionary of new risk limit values
        """
        try:
            for key, value in new_limits.items():
                if hasattr(self.risk_limits, key):
                    setattr(self.risk_limits, key, value)
                    logger.info(f"Updated risk limit {key}: {value}")
            
        except Exception as e:
            logger.error(f"Error updating risk limits: {e}")
    
    async def calculate_var(self, portfolio_value: float, confidence_level: float = 0.95) -> float:
        """
        Calculate Value at Risk (VaR) for the portfolio
        
        Args:
            portfolio_value: Current portfolio value
            confidence_level: Confidence level for VaR calculation
            
        Returns:
            VaR amount
        """
        try:
            # Simplified VaR calculation
            # In a real implementation, this would use historical returns
            # and correlation data
            
            volatility = 0.02  # 2% daily volatility
            z_score = 1.645 if confidence_level == 0.95 else 2.326  # 99% confidence
            
            var = portfolio_value * volatility * z_score
            
            return var
            
        except Exception as e:
            logger.error(f"Error calculating VaR: {e}")
            return 0.0
