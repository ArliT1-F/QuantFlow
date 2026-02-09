"""
Risk management system for controlling trading risk
"""
import logging
from typing import Dict, Optional, Any, Tuple, List
from datetime import datetime
import numpy as np
from dataclasses import dataclass

from app.core.config import settings
from app.strategies.base_strategy import Signal
from app.core.database import SessionLocal
from app.models.portfolio import PortfolioSnapshot

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
        self.position_correlations: Dict[str, float] = {}
        self.sector_exposures: Dict[str, float] = {}
        self.portfolio_manager = portfolio_manager
        self.peak_portfolio_value = max(self._get_portfolio_value(), 0.0)
        self.last_drawdown = 0.0

        # Sync limits from settings
        self.risk_limits.max_position_size = settings.MAX_POSITION_SIZE
        self.risk_limits.max_portfolio_risk = settings.MAX_PORTFOLIO_RISK
        self.risk_limits.max_daily_trades = settings.MAX_DAILY_TRADES
        self.risk_limits.min_volume = settings.MIN_VOLUME
        
        logger.info("Risk manager initialized")
    
    async def validate_signal(self, signal: Signal) -> Tuple[bool, str]:
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

            if not await self._check_portfolio_risk_limit(signal):
                return False, "portfolio risk limit exceeded"
            
            # Check sector exposure limits
            if not await self._check_sector_exposure_limit(signal):
                return False, "position concentration limit exceeded"
            
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
            if signal.action == "SELL":
                return True
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
            if signal.action == "SELL":
                return True
            metadata = signal.metadata or {}
            closes_by_symbol = metadata.get("closes_by_symbol", {})
            candidate_closes = closes_by_symbol.get(signal.symbol)
            open_symbols = []
            if self.portfolio_manager:
                open_symbols = [s for s, pos in self.portfolio_manager.positions.items() if pos.get("quantity", 0) > 0]

            if not candidate_closes or len(open_symbols) == 0:
                self.position_correlations = {}
                return True

            candidate_returns = self._to_returns(candidate_closes)
            if len(candidate_returns) < 3:
                self.position_correlations = {}
                return True

            computed: Dict[str, float] = {}
            for sym in open_symbols:
                closes = closes_by_symbol.get(sym)
                if not closes:
                    continue
                other_returns = self._to_returns(closes)
                min_len = min(len(candidate_returns), len(other_returns))
                if min_len < 3:
                    continue
                corr = np.corrcoef(candidate_returns[-min_len:], other_returns[-min_len:])[0, 1]
                if np.isnan(corr):
                    continue
                computed[sym] = float(corr)
                if abs(corr) > self.risk_limits.max_correlation:
                    self.position_correlations = computed
                    return False

            self.position_correlations = computed
            return True
            
        except Exception as e:
            logger.error(f"Error checking correlation limit: {e}")
            return True
    
    async def _check_sector_exposure_limit(self, signal: Signal) -> bool:
        """Check if single-asset exposure limit is exceeded."""
        try:
            if not self.portfolio_manager:
                return True
            portfolio_value = self._get_portfolio_value()
            if portfolio_value <= 0:
                return False

            exposures = self._compute_symbol_exposures(portfolio_value)
            if signal.action == "SELL":
                self.sector_exposures = exposures
                return True
            quantity = signal.quantity if signal.quantity is not None else await self.calculate_position_size(signal)
            if signal.action == "BUY" and quantity > 0 and signal.price > 0:
                projected_value = exposures.get(signal.symbol, 0.0) * portfolio_value + (quantity * signal.price)
                projected_exposure = projected_value / portfolio_value
                exposures[signal.symbol] = projected_exposure
            self.sector_exposures = exposures
            return max(exposures.values(), default=0.0) <= self.risk_limits.max_sector_exposure
            
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
            if signal.action == "SELL":
                if self.portfolio_manager and signal.symbol in self.portfolio_manager.positions:
                    return float(max(self.portfolio_manager.positions[signal.symbol].get("quantity", 0.0), 0.0))
                return 0.0
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

            symbol = trade_data.get("symbol", "")
            portfolio_value = self._get_portfolio_value()
            if portfolio_value > 0:
                self.peak_portfolio_value = max(self.peak_portfolio_value, portfolio_value)
                self.sector_exposures = self._compute_symbol_exposures(portfolio_value)
            
            logger.info(f"Trade recorded: {symbol}, Daily trades: {self.daily_trades}, Daily P&L: {self.daily_pnl}")
            
        except Exception as e:
            logger.error(f"Error recording trade: {e}")
    
    async def check_risk_limits(self) -> Tuple[bool, str]:
        """Check all risk limits and return whether trading can continue."""
        try:
            self._reset_daily_counters_if_needed()
            portfolio_value = self._get_portfolio_value()
            if portfolio_value <= 0:
                return False, "portfolio value is non-positive"

            self.peak_portfolio_value = max(self.peak_portfolio_value, portfolio_value)
            max_daily_loss_amount = portfolio_value * self.risk_limits.max_daily_loss
            if self.daily_pnl <= -max_daily_loss_amount:
                reason = f"daily loss limit exceeded ({self.daily_pnl:.2f} <= -{max_daily_loss_amount:.2f})"
                logger.warning(reason)
                return False, reason

            self.last_drawdown = self._current_drawdown_ratio(portfolio_value)
            if self.last_drawdown > self.risk_limits.max_drawdown:
                reason = f"max drawdown exceeded ({self.last_drawdown:.4f} > {self.risk_limits.max_drawdown:.4f})"
                logger.warning(reason)
                return False, reason

            return True, ""
            
        except Exception as e:
            logger.error(f"Error checking risk limits: {e}")
            return False, "risk limit check failure"
    
    def get_risk_metrics(self) -> Dict[str, Any]:
        """Get current risk metrics"""
        self._reset_daily_counters_if_needed()
        portfolio_value = self._get_portfolio_value()
        if portfolio_value > 0:
            self.sector_exposures = self._compute_symbol_exposures(portfolio_value)
            self.last_drawdown = self._current_drawdown_ratio(portfolio_value)
        
        return {
            "daily_trades": self.daily_trades,
            "daily_pnl": self.daily_pnl,
            "max_daily_trades": self.risk_limits.max_daily_trades,
            "max_daily_loss": self.risk_limits.max_daily_loss,
            "max_position_size": self.risk_limits.max_position_size,
            "max_portfolio_risk": self.risk_limits.max_portfolio_risk,
            "max_drawdown": self.risk_limits.max_drawdown,
            "current_drawdown": self.last_drawdown,
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
            if portfolio_value <= 0:
                return 0.0
            if not self.portfolio_manager or not self.portfolio_manager.portfolio_id:
                return 0.0

            db = SessionLocal()
            snapshots = db.query(PortfolioSnapshot).filter(
                PortfolioSnapshot.portfolio_id == self.portfolio_manager.portfolio_id
            ).order_by(PortfolioSnapshot.timestamp.asc()).limit(1000).all()
            db.close()

            equity = [float(s.total_value) for s in snapshots if s.total_value is not None and s.total_value > 0]
            returns = self._to_returns(equity)
            if len(returns) < 5:
                return 0.0

            percentile = (1.0 - confidence_level) * 100.0
            var_return = np.percentile(np.array(returns, dtype=float), percentile)
            return float(abs(var_return) * portfolio_value)
            
        except Exception as e:
            logger.error(f"Error calculating VaR: {e}")
            return 0.0

    def _to_returns(self, values: List[float]) -> List[float]:
        returns: List[float] = []
        for i in range(1, len(values)):
            prev = values[i - 1]
            curr = values[i]
            if prev > 0:
                returns.append((curr - prev) / prev)
        return returns

    def _compute_symbol_exposures(self, portfolio_value: float) -> Dict[str, float]:
        if not self.portfolio_manager or portfolio_value <= 0:
            return {}
        exposures: Dict[str, float] = {}
        for symbol, pos in self.portfolio_manager.positions.items():
            qty = float(pos.get("quantity", 0.0))
            px = float(pos.get("current_price", 0.0))
            if qty <= 0 or px <= 0:
                continue
            exposures[symbol] = (qty * px) / portfolio_value
        return exposures

    def _current_drawdown_ratio(self, portfolio_value: float) -> float:
        if portfolio_value <= 0:
            return 1.0
        if self.peak_portfolio_value <= 0:
            return 0.0
        return max((self.peak_portfolio_value - portfolio_value) / self.peak_portfolio_value, 0.0)
