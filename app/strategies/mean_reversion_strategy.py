"""
Mean reversion trading strategy based on statistical analysis
"""
import pandas as pd
import numpy as np
from typing import Dict, Optional, Any
from datetime import datetime, timedelta
from scipy import stats

from app.strategies.base_strategy import BaseStrategy, Signal

class MeanReversionStrategy(BaseStrategy):
    """Mean reversion strategy that identifies overbought/oversold conditions"""
    
    def __init__(self):
        super().__init__("Mean Reversion Strategy")
        self.parameters = {
            "lookback_period": 20,  # Days to look back for mean calculation
            "std_threshold": 2.0,  # Standard deviations from mean
            "min_volume": 100000,  # Minimum volume requirement
            "rsi_oversold": 30,  # RSI oversold level
            "rsi_overbought": 70,  # RSI overbought level
            "bollinger_period": 20,  # Bollinger Bands period
            "bollinger_std": 2,  # Bollinger Bands standard deviation
            "min_confidence": 0.65  # Minimum confidence for signal
        }
    
    async def generate_signal(self, symbol: str, data: Dict[str, Any]) -> Optional[Signal]:
        """
        Generate mean reversion trading signal
        
        Args:
            symbol: Stock symbol
            data: Market data for the symbol
            
        Returns:
            Signal object or None
        """
        if not self.validate_data(data):
            return None
        
        try:
            # Calculate mean reversion indicators
            reversion_score = await self._calculate_reversion_score(symbol, data)
            
            if reversion_score is None:
                return None
            
            # Determine signal based on mean reversion
            signal = self._create_signal_from_reversion(symbol, data, reversion_score)
            
            return signal
            
        except Exception as e:
            print(f"Error generating mean reversion signal for {symbol}: {e}")
            return None
    
    async def _calculate_reversion_score(self, symbol: str, data: Dict[str, Any]) -> Optional[float]:
        """Calculate mean reversion score for the symbol"""
        try:
            price = data.get("price", 0)
            volume = data.get("volume", 0)
            high = data.get("high", price)
            low = data.get("low", price)
            
            if price <= 0 or volume <= 0:
                return None
            
            # Simulate historical data for mean calculation
            # In a real implementation, this would use actual historical data
            simulated_prices = self._simulate_price_history(price, 20)
            
            if len(simulated_prices) < 10:
                return None
            
            # Calculate statistical measures
            mean_price = np.mean(simulated_prices)
            std_price = np.std(simulated_prices)
            
            if std_price == 0:
                return None
            
            # Calculate z-score (how many standard deviations from mean)
            z_score = (price - mean_price) / std_price
            
            # Calculate Bollinger Bands position
            bb_position = self._calculate_bollinger_position(price, simulated_prices)
            
            # Calculate RSI (simplified)
            rsi = self._calculate_simple_rsi(simulated_prices)
            
            # Combine indicators for reversion score
            reversion_score = self._combine_reversion_indicators(z_score, bb_position, rsi)
            
            return reversion_score
            
        except Exception as e:
            print(f"Error calculating reversion score for {symbol}: {e}")
            return None
    
    def _simulate_price_history(self, current_price: float, days: int) -> np.ndarray:
        """Simulate price history for mean calculation"""
        # This is a simplified simulation - in reality, you'd use actual historical data
        np.random.seed(42)  # For reproducible results
        daily_returns = np.random.normal(0, 0.02, days)  # 2% daily volatility
        prices = [current_price]
        
        for return_rate in daily_returns:
            new_price = prices[-1] * (1 + return_rate)
            prices.append(new_price)
        
        return np.array(prices[1:])  # Exclude current price
    
    def _calculate_bollinger_position(self, price: float, prices: np.ndarray) -> float:
        """Calculate position within Bollinger Bands"""
        try:
            period = min(self.parameters["bollinger_period"], len(prices))
            recent_prices = prices[-period:]
            
            sma = np.mean(recent_prices)
            std = np.std(recent_prices)
            
            upper_band = sma + (self.parameters["bollinger_std"] * std)
            lower_band = sma - (self.parameters["bollinger_std"] * std)
            
            if upper_band == lower_band:
                return 0.5  # Neutral position
            
            # Position within bands (0 = lower band, 1 = upper band)
            position = (price - lower_band) / (upper_band - lower_band)
            return max(0, min(1, position))  # Clamp between 0 and 1
            
        except:
            return 0.5  # Neutral position
    
    def _calculate_simple_rsi(self, prices: np.ndarray) -> float:
        """Calculate simplified RSI"""
        try:
            if len(prices) < 14:
                return 50  # Neutral RSI
            
            recent_prices = prices[-14:]
            gains = []
            losses = []
            
            for i in range(1, len(recent_prices)):
                change = recent_prices[i] - recent_prices[i-1]
                if change > 0:
                    gains.append(change)
                    losses.append(0)
                else:
                    gains.append(0)
                    losses.append(-change)
            
            avg_gain = np.mean(gains) if gains else 0
            avg_loss = np.mean(losses) if losses else 0
            
            if avg_loss == 0:
                return 100
            
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))
            
            return rsi
            
        except:
            return 50  # Neutral RSI
    
    def _combine_reversion_indicators(self, z_score: float, bb_position: float, rsi: float) -> float:
        """Combine multiple indicators into a reversion score"""
        try:
            # Normalize z-score to 0-1 scale
            z_score_norm = min(abs(z_score) / 3.0, 1.0)  # Cap at 3 standard deviations
            
            # RSI position (0 = oversold, 1 = overbought)
            rsi_position = rsi / 100.0
            
            # Bollinger Bands position (0 = lower band, 1 = upper band)
            bb_score = abs(bb_position - 0.5) * 2  # Distance from center
            
            # Combine with weights
            combined_score = (
                z_score_norm * 0.4 +      # Z-score weight
                bb_score * 0.3 +           # Bollinger Bands weight
                abs(rsi_position - 0.5) * 2 * 0.3  # RSI weight
            )
            
            return min(combined_score, 1.0)
            
        except:
            return 0.0
    
    def _create_signal_from_reversion(self, symbol: str, data: Dict[str, Any], reversion_score: float) -> Optional[Signal]:
        """Create trading signal based on mean reversion score"""
        try:
            price = data.get("price", 0)
            volume = data.get("volume", 0)
            high = data.get("high", price)
            low = data.get("low", price)
            
            # Check if reversion signal is strong enough
            if reversion_score < self.parameters["min_confidence"]:
                return None
            
            # Check volume requirement
            if volume < self.parameters["min_volume"]:
                return None
            
            # Simulate historical data for signal determination
            simulated_prices = self._simulate_price_history(price, 20)
            mean_price = np.mean(simulated_prices)
            std_price = np.std(simulated_prices)
            z_score = (price - mean_price) / std_price if std_price > 0 else 0
            
            # Determine action based on mean reversion
            if z_score > self.parameters["std_threshold"]:
                # Price is significantly above mean - SELL signal (expect reversion down)
                action = "SELL"
                confidence = min(reversion_score, 1.0)
            elif z_score < -self.parameters["std_threshold"]:
                # Price is significantly below mean - BUY signal (expect reversion up)
                action = "BUY"
                confidence = min(reversion_score, 1.0)
            else:
                # Price is near mean - no signal
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
                    "strategy": "mean_reversion",
                    "reversion_score": reversion_score,
                    "z_score": z_score,
                    "mean_price": mean_price,
                    "std_price": std_price,
                    "volume": volume,
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
            
            return signal
            
        except Exception as e:
            print(f"Error creating mean reversion signal for {symbol}: {e}")
            return None