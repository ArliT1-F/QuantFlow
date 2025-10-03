# Trading Strategies Documentation

## Overview

The automated trading bot includes four sophisticated trading strategies, each designed to identify different market opportunities using various analytical approaches.

## Strategy Framework

All strategies inherit from the `BaseStrategy` class and implement the following interface:

```python
class BaseStrategy(ABC):
    @abstractmethod
    async def generate_signal(self, symbol: str, data: Dict[str, Any]) -> Optional[Signal]:
        pass
```

Each strategy returns a `Signal` object containing:
- `symbol`: Stock symbol
- `action`: BUY, SELL, or HOLD
- `confidence`: Signal strength (0-1)
- `price`: Current price
- `quantity`: Suggested position size
- `stop_loss`: Stop loss price
- `take_profit`: Take profit price
- `metadata`: Additional strategy-specific data

## 1. Momentum Strategy

### Overview
The Momentum Strategy identifies stocks with strong upward or downward momentum based on price movement and volume analysis.

### Key Features
- **Price Momentum**: Analyzes recent price changes
- **Volume Confirmation**: Requires above-average volume
- **RSI Integration**: Uses RSI for overbought/oversold conditions
- **Trend Following**: Captures trending movements

### Parameters
```python
{
    "lookback_period": 20,        # Days to look back for momentum calculation
    "momentum_threshold": 0.05,   # Minimum momentum threshold (5%)
    "volume_threshold": 1.5,      # Volume must be 1.5x average
    "rsi_oversold": 30,          # RSI oversold level
    "rsi_overbought": 70,        # RSI overbought level
    "min_confidence": 0.6         # Minimum confidence for signal
}
```

### Signal Generation Logic

1. **Calculate Momentum Score**:
   - Price momentum: `abs(change_percent) / 100`
   - Volume momentum: `volume / average_volume`
   - Combined score: `(price_momentum * 0.7) + (volume_momentum * 0.3)`

2. **Signal Conditions**:
   - **BUY**: Strong upward momentum (>5%) + high volume + momentum score > 0.6
   - **SELL**: Strong downward momentum (<-5%) + high volume + momentum score > 0.6
   - **HOLD**: Insufficient momentum or conflicting signals

3. **Risk Management**:
   - Stop loss: 5% below entry price (BUY) or 5% above entry price (SELL)
   - Take profit: 15% above entry price (BUY) or 15% below entry price (SELL)

### Best Use Cases
- Trending markets
- High-volume stocks
- Breakout scenarios
- Strong earnings announcements

### Limitations
- May generate false signals in choppy markets
- Requires significant price movement
- Can be late to trend reversals

## 2. Mean Reversion Strategy

### Overview
The Mean Reversion Strategy identifies overbought/oversold conditions and expects prices to revert to their mean.

### Key Features
- **Statistical Analysis**: Uses z-scores and standard deviations
- **Bollinger Bands**: Identifies price extremes
- **RSI Integration**: Confirms overbought/oversold conditions
- **Mean Reversion**: Expects prices to return to average

### Parameters
```python
{
    "lookback_period": 20,        # Days for mean calculation
    "std_threshold": 2.0,         # Standard deviations from mean
    "min_volume": 100000,        # Minimum volume requirement
    "rsi_oversold": 30,          # RSI oversold level
    "rsi_overbought": 70,        # RSI overbought level
    "bollinger_period": 20,      # Bollinger Bands period
    "bollinger_std": 2,           # Bollinger Bands standard deviation
    "min_confidence": 0.65        # Minimum confidence for signal
}
```

### Signal Generation Logic

1. **Calculate Mean Reversion Score**:
   - Z-score: `(price - mean_price) / std_price`
   - Bollinger position: Position within bands (0-1)
   - RSI position: RSI level (0-1)
   - Combined score: Weighted combination of indicators

2. **Signal Conditions**:
   - **BUY**: Price significantly below mean (z-score < -2) + oversold RSI + near lower Bollinger Band
   - **SELL**: Price significantly above mean (z-score > 2) + overbought RSI + near upper Bollinger Band
   - **HOLD**: Price near mean or conflicting signals

3. **Risk Management**:
   - Stop loss: 5% below entry price (BUY) or 5% above entry price (SELL)
   - Take profit: 15% above entry price (BUY) or 15% below entry price (SELL)

### Best Use Cases
- Range-bound markets
- High-frequency trading
- Volatile stocks with mean-reverting behavior
- After significant price moves

### Limitations
- May fail in strong trending markets
- Requires sufficient volatility
- Can generate many small losses

## 3. Technical Analysis Strategy

### Overview
The Technical Analysis Strategy combines multiple technical indicators to generate comprehensive trading signals.

### Key Features
- **Multiple Indicators**: SMA, EMA, MACD, RSI, Bollinger Bands
- **Signal Confirmation**: Requires multiple indicators to agree
- **Volume Analysis**: Confirms signals with volume
- **Trend Analysis**: Identifies trend direction and strength

### Parameters
```python
{
    "sma_short": 10,             # Short-term SMA period
    "sma_long": 30,              # Long-term SMA period
    "rsi_period": 14,            # RSI period
    "rsi_oversold": 30,         # RSI oversold level
    "rsi_overbought": 70,       # RSI overbought level
    "macd_fast": 12,            # MACD fast period
    "macd_slow": 26,            # MACD slow period
    "macd_signal": 9,           # MACD signal period
    "bb_period": 20,            # Bollinger Bands period
    "bb_std": 2,                # Bollinger Bands standard deviation
    "min_confidence": 0.7,       # Minimum confidence for signal
    "min_volume": 100000        # Minimum volume requirement
}
```

### Signal Generation Logic

1. **Calculate Technical Indicators**:
   - Moving Averages: SMA(10), SMA(30), EMA(12), EMA(26)
   - MACD: MACD line, Signal line, Histogram
   - RSI: 14-period RSI
   - Bollinger Bands: Upper, Middle, Lower bands
   - Volume: Volume SMA and ratio

2. **Signal Scoring System**:
   - **Moving Average Signals**: SMA crossover (0.3 weight)
   - **RSI Signals**: Overbought/oversold (0.4 weight)
   - **MACD Signals**: MACD crossover (0.3 weight)
   - **Bollinger Bands**: Band extremes (0.2 weight)
   - **Volume Confirmation**: High volume multiplier (1.2x)

3. **Signal Conditions**:
   - **BUY**: Combined score > 0.7 + bullish indicators + volume confirmation
   - **SELL**: Combined score > 0.7 + bearish indicators + volume confirmation
   - **HOLD**: Insufficient signal strength or conflicting indicators

### Best Use Cases
- Medium-term trading
- Stocks with clear technical patterns
- Markets with good liquidity
- Trend-following strategies

### Limitations
- Can generate conflicting signals
- Requires multiple confirmations
- May be slow to react to sudden changes

## 4. Machine Learning Strategy

### Overview
The ML Strategy uses machine learning (Random Forest) to predict price movements based on multiple features.

### Key Features
- **Feature Engineering**: Price, volume, and technical indicators
- **Random Forest Model**: Ensemble learning for robust predictions
- **Probability Output**: Provides confidence levels
- **Adaptive Learning**: Retrains periodically with new data

### Parameters
```python
{
    "lookback_period": 20,        # Days for feature calculation
    "prediction_horizon": 5,      # Days ahead to predict
    "min_confidence": 0.65,       # Minimum confidence for signal
    "min_volume": 100000,        # Minimum volume requirement
    "model_retrain_days": 30,    # Retrain model every N days
    "feature_window": 10          # Window for feature calculation
}
```

### Feature Engineering

1. **Price Features**:
   - Price momentum (5-day)
   - Price vs SMA ratios (5, 10, 20-day)
   - Volatility (10-day standard deviation)
   - Price range (5-day high-low)

2. **Volume Features**:
   - Volume momentum (5-day)
   - Volume ratio (current vs 20-day average)
   - Volume trend

3. **Technical Features**:
   - RSI (14-day)
   - Market condition score

### Signal Generation Logic

1. **Feature Calculation**:
   - Generate 10 features from historical data
   - Normalize features using StandardScaler
   - Handle missing data appropriately

2. **Model Prediction**:
   - Use Random Forest classifier
   - Predict probabilities for SELL (0), HOLD (1), BUY (2)
   - Select highest probability class

3. **Signal Conditions**:
   - **BUY**: Predicted class = BUY + confidence > 0.65
   - **SELL**: Predicted class = SELL + confidence > 0.65
   - **HOLD**: Predicted class = HOLD or confidence < 0.65

### Model Training

1. **Data Generation**:
   - Synthetic training data (in production, use real historical data)
   - 1000 samples with 10 features
   - Balanced classes with some patterns

2. **Model Configuration**:
   - Random Forest with 100 estimators
   - Max depth of 10
   - Random state for reproducibility

3. **Retraining Schedule**:
   - Retrain every 30 days
   - Update with recent market data
   - Save model and scaler

### Best Use Cases
- Complex market conditions
- Multi-factor analysis
- Adaptive to changing market dynamics
- Quantitative trading approaches

### Limitations
- Requires sufficient historical data
- May overfit to training data
- Computational complexity
- Black box nature (hard to interpret)

## Strategy Performance Monitoring

### Metrics Tracked

1. **Trade Metrics**:
   - Total trades
   - Winning trades
   - Losing trades
   - Win rate

2. **Performance Metrics**:
   - Total P&L
   - Sharpe ratio
   - Maximum drawdown
   - Average trade size

3. **Risk Metrics**:
   - Average risk per trade
   - Maximum consecutive losses
   - Volatility of returns

### Performance Evaluation

Each strategy maintains performance metrics that are updated after each trade:

```python
def update_performance(self, trade_result: Dict[str, Any]):
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
```

## Strategy Configuration

### Enabling/Disabling Strategies

Edit `app/core/config.py`:

```python
ENABLED_STRATEGIES = [
    "momentum",           # Enable momentum strategy
    "mean_reversion",     # Enable mean reversion strategy
    "technical_analysis", # Enable technical analysis strategy
    "ml_strategy"         # Enable ML strategy
]
```

### Customizing Parameters

Each strategy can be customized by modifying its parameters:

```python
# In strategy initialization
self.parameters = {
    "lookback_period": 20,
    "momentum_threshold": 0.05,
    # ... other parameters
}
```

### Adding New Strategies

1. **Create Strategy Class**:
```python
class CustomStrategy(BaseStrategy):
    def __init__(self):
        super().__init__("Custom Strategy")
        self.parameters = {...}
    
    async def generate_signal(self, symbol: str, data: Dict[str, Any]) -> Optional[Signal]:
        # Implementation
        pass
```

2. **Register Strategy**:
```python
# In trading_engine.py
strategy_classes = {
    "custom": CustomStrategy,
    # ... other strategies
}
```

3. **Enable Strategy**:
```python
# In config.py
ENABLED_STRATEGIES = ["custom", ...]
```

## Risk Management Integration

All strategies integrate with the risk management system:

1. **Position Sizing**: Risk manager calculates optimal position size
2. **Stop Loss**: Strategies suggest stop loss levels
3. **Take Profit**: Strategies suggest take profit levels
4. **Risk Validation**: Risk manager validates all signals

## Backtesting

While not implemented in this version, backtesting capabilities should be added:

1. **Historical Data**: Use historical market data
2. **Strategy Simulation**: Run strategies on historical data
3. **Performance Analysis**: Calculate metrics and statistics
4. **Optimization**: Optimize strategy parameters

## Best Practices

1. **Parameter Tuning**: Test parameters on historical data
2. **Risk Management**: Always use stop losses and position sizing
3. **Diversification**: Use multiple strategies for diversification
4. **Monitoring**: Continuously monitor strategy performance
5. **Adaptation**: Adjust strategies based on market conditions

## Troubleshooting

### Common Issues

1. **No Signals Generated**:
   - Check parameter thresholds
   - Verify market data availability
   - Review confidence requirements

2. **Too Many Signals**:
   - Increase confidence thresholds
   - Add additional filters
   - Review market conditions

3. **Poor Performance**:
   - Analyze individual trade results
   - Review strategy parameters
   - Consider market regime changes

### Debugging

Enable debug logging for strategies:

```python
import logging
logger = logging.getLogger(__name__)
logger.debug(f"Strategy signal: {signal}")
```

Monitor strategy performance through the web dashboard or API endpoints.