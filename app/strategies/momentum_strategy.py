"""
Momentum trading strategy based on price and volume momentum
"""
import numpy as np
import pandas as pd
from typing import Dict, Optional, Any
from datetime import datetime
import logging

from app.strategies.base_strategy import BaseStrategy, Signal
logger = logging.getLogger(__name__)

class MomentumStrategy(BaseStrategy):
    """Momentum strategy that identifies coins with strong upward or downward momentum"""
    
    def __init__(self):
        super().__init__("Momentum Strategy")
        self.parameters = {
            "lookback_period": 14,  # Days to look back for momentum calculation
            "momentum_threshold": 0.005,  # Minimum momentum threshold (0.5%)
            "volume_threshold": 1.0,  # Volume confirmation (1.0x = enabled, not restrictive)
            "rsi_oversold": 30,  # RSI oversold level
            "rsi_overbought": 80,  # RSI overbought level
            "min_confidence": 0.5  # Minimum confidence for signal
        }
    
    async def generate_signal(self, symbol: str, data: Dict[str, Any]) -> Optional[Signal]:
        """
        Generate momentum-based trading signal
        
        Args:
            symbol: Coin symbol
            data: Market data for the symbol
            
        Returns:
            Signal object or None
        """
        if not self.validate_data(data):
            return None
        
        try:
            # Calculate momentum indicators
            momentum_data = await self._calculate_momentum_metrics(symbol, data)
            
            if not momentum_data:
                return None
            
            # Determine signal based on momentum
            signal = self._create_signal_from_momentum(symbol, data, momentum_data)
            
            return signal
            
        except Exception as e:
            logger.error(f"Error generating momentum signal for {symbol}: {e}")
            return None
    
    async def _calculate_momentum_metrics(self, symbol: str, data: Dict[str, Any]) -> Optional[Dict[str, float]]:
        """Calculate momentum metrics for the symbol using recent history"""
        try:
            history = data.get("history", [])
            if history and len(history) >= 2:
                closes = np.array([h["close"] for h in history])
                volumes = np.array([h["volume"] for h in history])

                price = closes[-1]
                volume = volumes[-1]
                if price <= 0 or volume <= 0:
                    return None

                lookback = min(self.parameters["lookback_period"], len(closes) - 1)
                price_then = closes[-1 - lookback]
                history_momentum = (price - price_then) / price_then if price_then > 0 else 0.0
                market_change_momentum = float(data.get("change_percent") or 0.0) / 100.0
                momentum = history_momentum
                if len(closes) < self.parameters["lookback_period"] + 1 and abs(market_change_momentum) > abs(history_momentum):
                    momentum = market_change_momentum
                volume_window = max(lookback, 1)
                volume_avg = np.mean(volumes[-volume_window:])
                volume_ratio = volume / volume_avg if volume_avg > 0 else 0.0

                rsi = self._calculate_rsi(pd.Series(closes))

                return {
                    "momentum": momentum,
                    "volume_ratio": volume_ratio,
                    "rsi": rsi,
                    "price": price,
                    "volume": volume,
                    "short_history": len(closes) < self.parameters["lookback_period"] + 1
                }

            # Fallback path for startup/short history: use 24h change as momentum proxy.
            price = float(data.get("price") or 0.0)
            volume = float(data.get("volume") or 0.0)
            if price <= 0 or volume <= 0:
                return None
            change_pct = float(data.get("change_percent") or 0.0) / 100.0
            return {
                "momentum": change_pct,
                "volume_ratio": 1.0,
                "rsi": 50.0,
                "price": price,
                "volume": volume,
                "short_history": True
            }
            
        except Exception as e:
            logger.error(f"Error calculating momentum score for {symbol}: {e}")
            return None
    
    def _create_signal_from_momentum(self, symbol: str, data: Dict[str, Any], momentum_data: Dict[str, float]) -> Optional[Signal]:
        """Create trading signal based on momentum metrics"""
        try:
            price = momentum_data["price"]
            volume = momentum_data["volume"]
            momentum = momentum_data["momentum"]
            volume_ratio = momentum_data["volume_ratio"]
            rsi = momentum_data["rsi"]
            short_history = bool(momentum_data.get("short_history", False))

            # Check volume threshold
            if volume_ratio < self.parameters["volume_threshold"]:
                return None

            # Determine action based on momentum direction with RSI filter
            if momentum > self.parameters["momentum_threshold"] and (short_history or rsi < self.parameters["rsi_overbought"]):
                # Strong upward momentum - BUY signal
                action = "BUY"
            elif momentum < -self.parameters["momentum_threshold"] and (short_history or rsi > self.parameters["rsi_oversold"]):
                # Strong downward momentum - SELL signal
                action = "SELL"
            else:
                # Insufficient momentum
                return None

            confidence_denominator = self.parameters["momentum_threshold"] if short_history else (self.parameters["momentum_threshold"] * 1.5)
            confidence = min(
                abs(momentum) / max(confidence_denominator, 1e-9),
                1.0
            )
            min_confidence = self.parameters["min_confidence"] if not short_history else (self.parameters["min_confidence"] * 0.8)
            if confidence < min_confidence:
                return None

            if action == "SELL" and short_history:
                # Avoid short-history SELL churn before a position exists.
                return None

            if action == "SELL":
                confidence = min(
                    confidence,
                    1.0
                )
            
            # Calculate stop loss and take profit
            stop_loss = self.calculate_stop_loss(price, action)
            take_profit = self.calculate_take_profit(price, action)
            
            # Create signal
            signal = Signal(
                symbol=symbol,
                action=action,
                confidence=confidence,
                price=price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                metadata={
                    "strategy": "momentum",
                    "momentum": momentum,
                    "volume_ratio": volume_ratio,
                    "rsi": rsi,
                    "volume": volume,
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
            
            return signal
            
        except Exception as e:
            logger.error(f"Error creating momentum signal for {symbol}: {e}")
            return None
    
    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> float:
        """Calculate RSI indicator"""
        try:
            delta = prices.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            return rsi.iloc[-1] if not rsi.empty else 50
        except:
            return 50  # Default neutral RSI
    
    def _calculate_moving_average(self, prices: pd.Series, period: int) -> float:
        """Calculate simple moving average"""
        try:
            return prices.rolling(window=period).mean().iloc[-1] if len(prices) >= period else prices.mean()
        except:
            return prices.mean() if not prices.empty else 0
