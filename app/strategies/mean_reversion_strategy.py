"""
Mean reversion trading strategy based on statistical analysis
"""
import numpy as np
from typing import Dict, Optional, Any
from datetime import datetime

from app.strategies.base_strategy import BaseStrategy, Signal

class MeanReversionStrategy(BaseStrategy):
    """Mean reversion strategy that identifies overbought/oversold conditions"""
    
    def __init__(self):
        super().__init__("Mean Reversion Strategy")
        self.parameters = {
            "lookback_period": 20,  # Days to look back for mean calculation
            "std_threshold": 1.0,  # Standard deviations from mean
            "min_volume_ratio": 0.8,  # Current volume vs avg volume
            "rsi_oversold": 30,  # RSI oversold level
            "rsi_overbought": 70,  # RSI overbought level
            "bollinger_period": 20,  # Bollinger Bands period
            "bollinger_std": 2,  # Bollinger Bands standard deviation
            "min_confidence": 0.5  # Minimum confidence for signal
        }
    
    async def generate_signal(self, symbol: str, data: Dict[str, Any]) -> Optional[Signal]:
        """
        Generate mean reversion trading signal
        
        Args:
            symbol: Coin symbol
            data: Market data for the symbol
            
        Returns:
            Signal object or None
        """
        if not self.validate_data(data):
            return None
        
        try:
            # Calculate mean reversion indicators
            reversion_data = await self._calculate_reversion_score(symbol, data)
            
            if not reversion_data:
                return None
            
            # Determine signal based on mean reversion
            signal = self._create_signal_from_reversion(symbol, data, reversion_data)
            
            return signal
            
        except Exception as e:
            print(f"Error generating mean reversion signal for {symbol}: {e}")
            return None
    
    async def _calculate_reversion_score(self, symbol: str, data: Dict[str, Any]) -> Optional[float]:
        """Calculate mean reversion score for the symbol"""
        try:
            history = data.get("history", [])
            if not history or len(history) < self.parameters["lookback_period"] + 1:
                return None

            closes = np.array([h["close"] for h in history])
            price = closes[-1]
            volume = history[-1].get("volume", 0)
            if price <= 0 or volume <= 0:
                return None

            recent_prices = closes[-self.parameters["lookback_period"]:]
            recent_volumes = np.array([h["volume"] for h in history])[-self.parameters["lookback_period"]:]

            # Calculate statistical measures
            mean_price = np.mean(recent_prices)
            std_price = np.std(recent_prices)
            
            if std_price == 0:
                return None
            
            # Calculate z-score (how many standard deviations from mean)
            z_score = (price - mean_price) / std_price
            
            # Calculate Bollinger Bands position
            bb_position = self._calculate_bollinger_position(price, recent_prices)
            
            # Calculate RSI (simplified)
            rsi = self._calculate_simple_rsi(recent_prices)
            
            # Combine indicators for reversion score
            reversion_score = self._combine_reversion_indicators(z_score, bb_position, rsi)
            volume_ratio = (volume / np.mean(recent_volumes)) if np.mean(recent_volumes) > 0 else 0.0
            
            return {
                "score": reversion_score,
                "price": price,
                "volume": volume,
                "volume_ratio": volume_ratio,
                "z_score": z_score,
                "mean_price": mean_price,
                "std_price": std_price
            }
            
        except Exception as e:
            print(f"Error calculating reversion score for {symbol}: {e}")
            return None
    
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
    
    def _create_signal_from_reversion(self, symbol: str, data: Dict[str, Any], reversion_data: Dict[str, float]) -> Optional[Signal]:
        """Create trading signal based on mean reversion score"""
        try:
            history = data.get("history", [])
            if not history or len(history) < self.parameters["lookback_period"] + 1:
                return None

            price = reversion_data["price"]
            volume = reversion_data["volume"]
            
            # Check if reversion signal is strong enough
            if reversion_data["score"] < self.parameters["min_confidence"]:
                return None
            
            # Check volume ratio requirement
            if reversion_data["volume_ratio"] < self.parameters["min_volume_ratio"]:
                return None
            
            mean_price = reversion_data["mean_price"]
            std_price = reversion_data["std_price"]
            z_score = reversion_data["z_score"]
            
            # Determine action based on mean reversion
            if z_score > self.parameters["std_threshold"]:
                # Price is significantly above mean - SELL signal (expect reversion down)
                action = "SELL"
                confidence = min(reversion_data["score"], 1.0)
            elif z_score < -self.parameters["std_threshold"]:
                # Price is significantly below mean - BUY signal (expect reversion up)
                action = "BUY"
                confidence = min(reversion_data["score"], 1.0)
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
                    "reversion_score": reversion_data["score"],
                    "z_score": z_score,
                    "mean_price": mean_price,
                    "std_price": std_price,
                    "volume_ratio": reversion_data["volume_ratio"],
                    "volume": volume,
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
            
            return signal
            
        except Exception as e:
            print(f"Error creating mean reversion signal for {symbol}: {e}")
            return None
