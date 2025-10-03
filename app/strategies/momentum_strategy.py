"""
Momentum trading strategy based on price and volume momentum
"""
import pandas as pd
import numpy as np
from typing import Dict, Optional, Any
from datetime import datetime, timedelta

from app.strategies.base_strategy import BaseStrategy, Signal

class MomentumStrategy(BaseStrategy):
    """Momentum strategy that identifies stocks with strong upward or downward momentum"""
    
    def __init__(self):
        super().__init__("Momentum Strategy")
        self.parameters = {
            "lookback_period": 20,  # Days to look back for momentum calculation
            "momentum_threshold": 0.05,  # Minimum momentum threshold (5%)
            "volume_threshold": 1.5,  # Volume must be 1.5x average
            "rsi_oversold": 30,  # RSI oversold level
            "rsi_overbought": 70,  # RSI overbought level
            "min_confidence": 0.6  # Minimum confidence for signal
        }
    
    async def generate_signal(self, symbol: str, data: Dict[str, Any]) -> Optional[Signal]:
        """
        Generate momentum-based trading signal
        
        Args:
            symbol: Stock symbol
            data: Market data for the symbol
            
        Returns:
            Signal object or None
        """
        if not self.validate_data(data):
            return None
        
        try:
            # Calculate momentum indicators
            momentum_score = await self._calculate_momentum_score(symbol, data)
            
            if momentum_score is None:
                return None
            
            # Determine signal based on momentum
            signal = self._create_signal_from_momentum(symbol, data, momentum_score)
            
            return signal
            
        except Exception as e:
            print(f"Error generating momentum signal for {symbol}: {e}")
            return None
    
    async def _calculate_momentum_score(self, symbol: str, data: Dict[str, Any]) -> Optional[float]:
        """Calculate momentum score for the symbol"""
        try:
            # This would typically use historical data
            # For now, we'll use current data to simulate momentum
            
            price = data.get("price", 0)
            volume = data.get("volume", 0)
            change_percent = data.get("change_percent", 0)
            
            if price <= 0 or volume <= 0:
                return None
            
            # Simple momentum calculation based on price change and volume
            price_momentum = abs(change_percent) / 100  # Normalize to 0-1
            
            # Volume momentum (simplified)
            volume_momentum = min(volume / 1000000, 1.0)  # Normalize volume
            
            # Combined momentum score
            momentum_score = (price_momentum * 0.7) + (volume_momentum * 0.3)
            
            return momentum_score
            
        except Exception as e:
            print(f"Error calculating momentum score for {symbol}: {e}")
            return None
    
    def _create_signal_from_momentum(self, symbol: str, data: Dict[str, Any], momentum_score: float) -> Optional[Signal]:
        """Create trading signal based on momentum score"""
        try:
            price = data.get("price", 0)
            change_percent = data.get("change_percent", 0)
            volume = data.get("volume", 0)
            
            # Check if momentum is strong enough
            if momentum_score < self.parameters["min_confidence"]:
                return None
            
            # Check volume threshold
            if volume < self.parameters["volume_threshold"] * 100000:  # Minimum volume
                return None
            
            # Determine action based on price direction
            if change_percent > self.parameters["momentum_threshold"] * 100:
                # Strong upward momentum - BUY signal
                action = "BUY"
                confidence = min(momentum_score, 1.0)
            elif change_percent < -self.parameters["momentum_threshold"] * 100:
                # Strong downward momentum - SELL signal
                action = "SELL"
                confidence = min(momentum_score, 1.0)
            else:
                # Insufficient momentum
                return None
            
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
                    "momentum_score": momentum_score,
                    "change_percent": change_percent,
                    "volume": volume,
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
            
            return signal
            
        except Exception as e:
            print(f"Error creating momentum signal for {symbol}: {e}")
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