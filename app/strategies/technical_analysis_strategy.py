"""
Technical analysis strategy based on multiple technical indicators
"""
import pandas as pd
import numpy as np
from typing import Dict, Optional, Any, List
from datetime import datetime, timedelta

from app.strategies.base_strategy import BaseStrategy, Signal

class TechnicalAnalysisStrategy(BaseStrategy):
    """Technical analysis strategy using multiple indicators"""
    
    def __init__(self):
        super().__init__("Technical Analysis Strategy")
        self.parameters = {
            "sma_short": 10,  # Short-term SMA period
            "sma_long": 30,   # Long-term SMA period
            "rsi_period": 14,  # RSI period
            "rsi_oversold": 30,  # RSI oversold level
            "rsi_overbought": 70,  # RSI overbought level
            "macd_fast": 12,   # MACD fast period
            "macd_slow": 26,   # MACD slow period
            "macd_signal": 9,  # MACD signal period
            "bb_period": 20,   # Bollinger Bands period
            "bb_std": 2,       # Bollinger Bands standard deviation
            "min_confidence": 0.7,  # Minimum confidence for signal
            "min_volume": 100000  # Minimum volume requirement
        }
    
    async def generate_signal(self, symbol: str, data: Dict[str, Any]) -> Optional[Signal]:
        """
        Generate technical analysis trading signal
        
        Args:
            symbol: Stock symbol
            data: Market data for the symbol
            
        Returns:
            Signal object or None
        """
        if not self.validate_data(data):
            return None
        
        try:
            # Calculate technical indicators
            indicators = await self._calculate_technical_indicators(symbol, data)
            
            if not indicators:
                return None
            
            # Generate signal based on indicators
            signal = self._create_signal_from_indicators(symbol, data, indicators)
            
            return signal
            
        except Exception as e:
            print(f"Error generating technical analysis signal for {symbol}: {e}")
            return None
    
    async def _calculate_technical_indicators(self, symbol: str, data: Dict[str, Any]) -> Optional[Dict[str, float]]:
        """Calculate technical indicators for the symbol"""
        try:
            price = data.get("price", 0)
            volume = data.get("volume", 0)
            high = data.get("high", price)
            low = data.get("low", price)
            
            if price <= 0 or volume <= 0:
                return None
            
            # Simulate historical data for indicator calculation
            historical_data = self._simulate_historical_data(price, high, low, volume, 50)
            
            if len(historical_data) < max(self.parameters["sma_long"], self.parameters["bb_period"]):
                return None
            
            indicators = {}
            
            # Moving Averages
            indicators["sma_short"] = self._calculate_sma(historical_data["close"], self.parameters["sma_short"])
            indicators["sma_long"] = self._calculate_sma(historical_data["close"], self.parameters["sma_long"])
            
            # RSI
            indicators["rsi"] = self._calculate_rsi(historical_data["close"], self.parameters["rsi_period"])
            
            # MACD
            macd_data = self._calculate_macd(historical_data["close"])
            indicators.update(macd_data)
            
            # Bollinger Bands
            bb_data = self._calculate_bollinger_bands(historical_data["close"])
            indicators.update(bb_data)
            
            # Volume indicators
            indicators["volume_sma"] = self._calculate_sma(historical_data["volume"], 20)
            indicators["volume_ratio"] = volume / indicators["volume_sma"] if indicators["volume_sma"] > 0 else 1
            
            # Price position indicators
            indicators["price_vs_sma_short"] = (price - indicators["sma_short"]) / indicators["sma_short"]
            indicators["price_vs_sma_long"] = (price - indicators["sma_long"]) / indicators["sma_long"]
            indicators["sma_cross"] = indicators["sma_short"] - indicators["sma_long"]
            
            return indicators
            
        except Exception as e:
            print(f"Error calculating technical indicators for {symbol}: {e}")
            return None
    
    def _simulate_historical_data(self, current_price: float, current_high: float, 
                                 current_low: float, current_volume: int, days: int) -> Dict[str, List[float]]:
        """Simulate historical data for indicator calculation"""
        np.random.seed(42)  # For reproducible results
        
        # Generate price data with some trend and volatility
        daily_returns = np.random.normal(0.001, 0.02, days)  # Slight upward bias, 2% volatility
        prices = [current_price]
        highs = [current_high]
        lows = [current_low]
        volumes = [current_volume]
        
        for i in range(days - 1):
            # Generate next price
            new_price = prices[-1] * (1 + daily_returns[i])
            prices.append(new_price)
            
            # Generate high/low (simplified)
            daily_range = abs(daily_returns[i]) * prices[-1]
            highs.append(new_price + daily_range * 0.3)
            lows.append(new_price - daily_range * 0.3)
            
            # Generate volume (with some correlation to price movement)
            volume_change = 1 + np.random.normal(0, 0.3)
            volumes.append(max(10000, int(volumes[-1] * volume_change)))
        
        return {
            "close": prices,
            "high": highs,
            "low": lows,
            "volume": volumes
        }
    
    def _calculate_sma(self, prices: List[float], period: int) -> float:
        """Calculate Simple Moving Average"""
        if len(prices) < period:
            return np.mean(prices)
        return np.mean(prices[-period:])
    
    def _calculate_rsi(self, prices: List[float], period: int = 14) -> float:
        """Calculate RSI indicator"""
        if len(prices) < period + 1:
            return 50  # Neutral RSI
        
        gains = []
        losses = []
        
        for i in range(1, len(prices)):
            change = prices[i] - prices[i-1]
            if change > 0:
                gains.append(change)
                losses.append(0)
            else:
                gains.append(0)
                losses.append(-change)
        
        if len(gains) < period:
            return 50
        
        avg_gain = np.mean(gains[-period:])
        avg_loss = np.mean(losses[-period:])
        
        if avg_loss == 0:
            return 100
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    def _calculate_macd(self, prices: List[float]) -> Dict[str, float]:
        """Calculate MACD indicator"""
        if len(prices) < self.parameters["macd_slow"]:
            return {"macd": 0, "macd_signal": 0, "macd_histogram": 0}
        
        # Calculate EMAs
        ema_fast = self._calculate_ema(prices, self.parameters["macd_fast"])
        ema_slow = self._calculate_ema(prices, self.parameters["macd_slow"])
        
        macd = ema_fast - ema_slow
        
        # Calculate MACD signal line (simplified)
        macd_signal = macd * 0.9  # Simplified signal calculation
        
        macd_histogram = macd - macd_signal
        
        return {
            "macd": macd,
            "macd_signal": macd_signal,
            "macd_histogram": macd_histogram
        }
    
    def _calculate_ema(self, prices: List[float], period: int) -> float:
        """Calculate Exponential Moving Average"""
        if len(prices) < period:
            return np.mean(prices)
        
        multiplier = 2 / (period + 1)
        ema = prices[0]
        
        for price in prices[1:]:
            ema = (price * multiplier) + (ema * (1 - multiplier))
        
        return ema
    
    def _calculate_bollinger_bands(self, prices: List[float]) -> Dict[str, float]:
        """Calculate Bollinger Bands"""
        if len(prices) < self.parameters["bb_period"]:
            return {"bb_upper": prices[-1], "bb_middle": prices[-1], "bb_lower": prices[-1]}
        
        recent_prices = prices[-self.parameters["bb_period"]:]
        middle = np.mean(recent_prices)
        std = np.std(recent_prices)
        
        upper = middle + (self.parameters["bb_std"] * std)
        lower = middle - (self.parameters["bb_std"] * std)
        
        return {
            "bb_upper": upper,
            "bb_middle": middle,
            "bb_lower": lower
        }
    
    def _create_signal_from_indicators(self, symbol: str, data: Dict[str, Any], indicators: Dict[str, float]) -> Optional[Signal]:
        """Create trading signal based on technical indicators"""
        try:
            price = data.get("price", 0)
            volume = data.get("volume", 0)
            
            # Check volume requirement
            if volume < self.parameters["min_volume"]:
                return None
            
            # Analyze indicators for signals
            signals = []
            
            # Moving Average signals
            if indicators["sma_short"] > indicators["sma_long"] and indicators["price_vs_sma_short"] > 0.01:
                signals.append(("BUY", 0.3, "SMA Bullish"))
            
            if indicators["sma_short"] < indicators["sma_long"] and indicators["price_vs_sma_short"] < -0.01:
                signals.append(("SELL", 0.3, "SMA Bearish"))
            
            # RSI signals
            if indicators["rsi"] < self.parameters["rsi_oversold"]:
                signals.append(("BUY", 0.4, "RSI Oversold"))
            elif indicators["rsi"] > self.parameters["rsi_overbought"]:
                signals.append(("SELL", 0.4, "RSI Overbought"))
            
            # MACD signals
            if indicators["macd"] > indicators["macd_signal"] and indicators["macd_histogram"] > 0:
                signals.append(("BUY", 0.3, "MACD Bullish"))
            elif indicators["macd"] < indicators["macd_signal"] and indicators["macd_histogram"] < 0:
                signals.append(("SELL", 0.3, "MACD Bearish"))
            
            # Bollinger Bands signals
            bb_position = (price - indicators["bb_lower"]) / (indicators["bb_upper"] - indicators["bb_lower"])
            if bb_position < 0.1:  # Near lower band
                signals.append(("BUY", 0.2, "BB Lower Band"))
            elif bb_position > 0.9:  # Near upper band
                signals.append(("SELL", 0.2, "BB Upper Band"))
            
            # Volume confirmation
            if indicators["volume_ratio"] > 1.5:  # High volume
                for i, (action, weight, reason) in enumerate(signals):
                    signals[i] = (action, weight * 1.2, reason + " + Volume")
            
            # Combine signals
            if not signals:
                return None
            
            # Calculate combined signal
            buy_signals = [s for s in signals if s[0] == "BUY"]
            sell_signals = [s for s in signals if s[0] == "SELL"]
            
            buy_strength = sum(s[1] for s in buy_signals)
            sell_strength = sum(s[1] for s in sell_signals)
            
            # Determine final signal
            if buy_strength > sell_strength and buy_strength > self.parameters["min_confidence"]:
                action = "BUY"
                confidence = min(buy_strength, 1.0)
                reasons = [s[2] for s in buy_signals]
            elif sell_strength > buy_strength and sell_strength > self.parameters["min_confidence"]:
                action = "SELL"
                confidence = min(sell_strength, 1.0)
                reasons = [s[2] for s in sell_signals]
            else:
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
                    "strategy": "technical_analysis",
                    "indicators": indicators,
                    "reasons": reasons,
                    "volume_ratio": indicators["volume_ratio"],
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
            
            return signal
            
        except Exception as e:
            print(f"Error creating technical analysis signal for {symbol}: {e}")
            return None