"""
Machine Learning based trading strategy
"""
import pandas as pd
import numpy as np
from typing import Dict, Optional, Any, List
from datetime import datetime, timedelta
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
import joblib
import os

from app.strategies.base_strategy import BaseStrategy, Signal

class MLStrategy(BaseStrategy):
    """Machine Learning strategy using Random Forest for signal generation"""
    
    def __init__(self):
        super().__init__("ML Strategy")
        self.parameters = {
            "lookback_period": 20,  # Days to look back for features
            "prediction_horizon": 5,  # Days ahead to predict
            "min_confidence": 0.65,  # Minimum confidence for signal
            "min_volume": 100000,  # Minimum volume requirement
            "model_retrain_days": 30,  # Retrain model every N days
            "feature_window": 10  # Window for feature calculation
        }
        
        self.model = None
        self.scaler = StandardScaler()
        self.last_retrain = None
        self.model_path = "models/ml_trading_model.pkl"
        self.scaler_path = "models/ml_scaler.pkl"
        
        # Initialize model
        self._load_or_create_model()
    
    async def generate_signal(self, symbol: str, data: Dict[str, Any]) -> Optional[Signal]:
        """
        Generate ML-based trading signal
        
        Args:
            symbol: Stock symbol
            data: Market data for the symbol
            
        Returns:
            Signal object or None
        """
        if not self.validate_data(data):
            return None
        
        try:
            # Check if model needs retraining
            await self._check_model_retrain()
            
            # Generate features
            features = await self._generate_features(symbol, data)
            
            if features is None:
                return None
            
            # Make prediction
            prediction = await self._make_prediction(features)
            
            if prediction is None:
                return None
            
            # Create signal from prediction
            signal = self._create_signal_from_prediction(symbol, data, prediction)
            
            return signal
            
        except Exception as e:
            print(f"Error generating ML signal for {symbol}: {e}")
            return None
    
    def _load_or_create_model(self):
        """Load existing model or create new one"""
        try:
            if os.path.exists(self.model_path) and os.path.exists(self.scaler_path):
                self.model = joblib.load(self.model_path)
                self.scaler = joblib.load(self.scaler_path)
                print("Loaded existing ML model")
            else:
                self._create_new_model()
                print("Created new ML model")
        except Exception as e:
            print(f"Error loading model: {e}")
            self._create_new_model()
    
    def _create_new_model(self):
        """Create a new ML model"""
        try:
            # Create a simple Random Forest model
            self.model = RandomForestClassifier(
                n_estimators=100,
                max_depth=10,
                random_state=42,
                n_jobs=-1
            )
            
            # Create dummy scaler
            dummy_data = np.random.randn(100, 10)
            self.scaler.fit(dummy_data)
            
            # Save model and scaler
            os.makedirs("models", exist_ok=True)
            joblib.dump(self.model, self.model_path)
            joblib.dump(self.scaler, self.scaler_path)
            
        except Exception as e:
            print(f"Error creating new model: {e}")
    
    async def _check_model_retrain(self):
        """Check if model needs retraining"""
        try:
            if self.last_retrain is None:
                self.last_retrain = datetime.utcnow()
                return
            
            days_since_retrain = (datetime.utcnow() - self.last_retrain).days
            
            if days_since_retrain >= self.parameters["model_retrain_days"]:
                await self._retrain_model()
                self.last_retrain = datetime.utcnow()
                
        except Exception as e:
            print(f"Error checking model retrain: {e}")
    
    async def _retrain_model(self):
        """Retrain the ML model with new data"""
        try:
            print("Retraining ML model...")
            
            # Generate synthetic training data
            # In a real implementation, this would use actual historical data
            X_train, y_train = self._generate_synthetic_training_data()
            
            if len(X_train) == 0:
                print("No training data available")
                return
            
            # Scale features
            X_train_scaled = self.scaler.fit_transform(X_train)
            
            # Train model
            self.model.fit(X_train_scaled, y_train)
            
            # Save updated model
            joblib.dump(self.model, self.model_path)
            joblib.dump(self.scaler, self.scaler_path)
            
            print("Model retrained successfully")
            
        except Exception as e:
            print(f"Error retraining model: {e}")
    
    def _generate_synthetic_training_data(self) -> tuple:
        """Generate synthetic training data for model training"""
        try:
            np.random.seed(42)
            
            # Generate synthetic features
            n_samples = 1000
            n_features = 10
            
            X = np.random.randn(n_samples, n_features)
            
            # Generate synthetic labels (0 = SELL, 1 = HOLD, 2 = BUY)
            # Create some patterns in the data
            y = np.random.choice([0, 1, 2], n_samples, p=[0.3, 0.4, 0.3])
            
            # Add some patterns based on features
            for i in range(n_samples):
                # If first few features are high, more likely to be BUY
                if np.mean(X[i, :3]) > 0.5:
                    y[i] = 2
                # If first few features are low, more likely to be SELL
                elif np.mean(X[i, :3]) < -0.5:
                    y[i] = 0
            
            return X, y
            
        except Exception as e:
            print(f"Error generating synthetic training data: {e}")
            return np.array([]), np.array([])
    
    async def _generate_features(self, symbol: str, data: Dict[str, Any]) -> Optional[np.ndarray]:
        """Generate features for ML model"""
        try:
            price = data.get("price", 0)
            volume = data.get("volume", 0)
            high = data.get("high", price)
            low = data.get("low", price)
            change_percent = data.get("change_percent", 0)
            
            if price <= 0 or volume <= 0:
                return None
            
            # Simulate historical data for feature calculation
            historical_data = self._simulate_historical_data(price, high, low, volume, self.parameters["lookback_period"])
            
            if len(historical_data["close"]) < self.parameters["feature_window"]:
                return None
            
            features = []
            
            # Price-based features
            prices = historical_data["close"]
            volumes = historical_data["volume"]
            
            # Price momentum features
            features.append(self._calculate_price_momentum(prices))
            features.append(self._calculate_volume_momentum(volumes))
            
            # Technical indicator features
            features.append(self._calculate_rsi(prices))
            features.append(self._calculate_price_vs_sma(prices, 5))
            features.append(self._calculate_price_vs_sma(prices, 10))
            features.append(self._calculate_price_vs_sma(prices, 20))
            
            # Volatility features
            features.append(self._calculate_volatility(prices))
            features.append(self._calculate_price_range(prices))
            
            # Volume features
            features.append(self._calculate_volume_ratio(volumes))
            features.append(self._calculate_volume_trend(volumes))
            
            # Market condition features
            features.append(self._calculate_market_condition(prices, volumes))
            
            return np.array(features).reshape(1, -1)
            
        except Exception as e:
            print(f"Error generating features for {symbol}: {e}")
            return None
    
    def _simulate_historical_data(self, current_price: float, current_high: float, 
                                 current_low: float, current_volume: int, days: int) -> Dict[str, List[float]]:
        """Simulate historical data for feature calculation"""
        np.random.seed(42)
        
        daily_returns = np.random.normal(0.001, 0.02, days)
        prices = [current_price]
        highs = [current_high]
        lows = [current_low]
        volumes = [current_volume]
        
        for i in range(days - 1):
            new_price = prices[-1] * (1 + daily_returns[i])
            prices.append(new_price)
            
            daily_range = abs(daily_returns[i]) * prices[-1]
            highs.append(new_price + daily_range * 0.3)
            lows.append(new_price - daily_range * 0.3)
            
            volume_change = 1 + np.random.normal(0, 0.3)
            volumes.append(max(10000, int(volumes[-1] * volume_change)))
        
        return {
            "close": prices,
            "high": highs,
            "low": lows,
            "volume": volumes
        }
    
    def _calculate_price_momentum(self, prices: List[float]) -> float:
        """Calculate price momentum"""
        if len(prices) < 5:
            return 0
        return (prices[-1] - prices[-5]) / prices[-5]
    
    def _calculate_volume_momentum(self, volumes: List[float]) -> float:
        """Calculate volume momentum"""
        if len(volumes) < 5:
            return 0
        return (volumes[-1] - volumes[-5]) / volumes[-5] if volumes[-5] > 0 else 0
    
    def _calculate_rsi(self, prices: List[float]) -> float:
        """Calculate RSI"""
        if len(prices) < 14:
            return 50
        
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
        
        if len(gains) < 14:
            return 50
        
        avg_gain = np.mean(gains[-14:])
        avg_loss = np.mean(losses[-14:])
        
        if avg_loss == 0:
            return 100
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi / 100  # Normalize to 0-1
    
    def _calculate_price_vs_sma(self, prices: List[float], period: int) -> float:
        """Calculate price vs SMA ratio"""
        if len(prices) < period:
            return 0
        sma = np.mean(prices[-period:])
        return (prices[-1] - sma) / sma if sma > 0 else 0
    
    def _calculate_volatility(self, prices: List[float]) -> float:
        """Calculate price volatility"""
        if len(prices) < 10:
            return 0
        returns = np.diff(prices[-10:]) / prices[-11:-1]
        return np.std(returns)
    
    def _calculate_price_range(self, prices: List[float]) -> float:
        """Calculate price range"""
        if len(prices) < 5:
            return 0
        recent_prices = prices[-5:]
        return (max(recent_prices) - min(recent_prices)) / min(recent_prices)
    
    def _calculate_volume_ratio(self, volumes: List[float]) -> float:
        """Calculate volume ratio"""
        if len(volumes) < 10:
            return 1
        recent_volume = volumes[-1]
        avg_volume = np.mean(volumes[-10:])
        return recent_volume / avg_volume if avg_volume > 0 else 1
    
    def _calculate_volume_trend(self, volumes: List[float]) -> float:
        """Calculate volume trend"""
        if len(volumes) < 5:
            return 0
        return (volumes[-1] - volumes[-5]) / volumes[-5] if volumes[-5] > 0 else 0
    
    def _calculate_market_condition(self, prices: List[float], volumes: List[float]) -> float:
        """Calculate overall market condition"""
        if len(prices) < 10:
            return 0
        
        # Simple market condition based on price trend and volume
        price_trend = (prices[-1] - prices[-10]) / prices[-10]
        volume_trend = (volumes[-1] - np.mean(volumes[-10:])) / np.mean(volumes[-10:])
        
        return (price_trend + volume_trend) / 2
    
    async def _make_prediction(self, features: np.ndarray) -> Optional[Dict[str, Any]]:
        """Make prediction using ML model"""
        try:
            if self.model is None:
                return None
            
            # Scale features
            features_scaled = self.scaler.transform(features)
            
            # Make prediction
            prediction = self.model.predict(features_scaled)[0]
            probabilities = self.model.predict_proba(features_scaled)[0]
            
            # Map prediction to action
            action_map = {0: "SELL", 1: "HOLD", 2: "BUY"}
            action = action_map.get(prediction, "HOLD")
            
            # Get confidence (probability of predicted class)
            confidence = probabilities[prediction]
            
            return {
                "action": action,
                "confidence": confidence,
                "probabilities": {
                    "SELL": probabilities[0],
                    "HOLD": probabilities[1],
                    "BUY": probabilities[2]
                }
            }
            
        except Exception as e:
            print(f"Error making ML prediction: {e}")
            return None
    
    def _create_signal_from_prediction(self, symbol: str, data: Dict[str, Any], prediction: Dict[str, Any]) -> Optional[Signal]:
        """Create trading signal from ML prediction"""
        try:
            action = prediction["action"]
            confidence = prediction["confidence"]
            probabilities = prediction["probabilities"]
            
            # Check minimum confidence
            if confidence < self.parameters["min_confidence"]:
                return None
            
            # Check volume requirement
            volume = data.get("volume", 0)
            if volume < self.parameters["min_volume"]:
                return None
            
            # Skip HOLD signals
            if action == "HOLD":
                return None
            
            price = data.get("price", 0)
            
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
                    "strategy": "ml_strategy",
                    "probabilities": probabilities,
                    "model_version": "1.0",
                    "volume": volume,
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
            
            return signal
            
        except Exception as e:
            print(f"Error creating ML signal for {symbol}: {e}")
            return None