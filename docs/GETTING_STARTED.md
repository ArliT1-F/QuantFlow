# Getting Started with the Automated Coin Trading Bot

## Overview

This automated coin trading bot is an educational, **paper-trading** system that provides:

- **Real-time Market Data**: DexScreener
- **Multiple Trading Strategies**: Momentum, Mean Reversion, and Technical Analysis
- **Risk Management**: Position sizing, stop-loss, take-profit, and portfolio risk controls
- **Web Dashboard**: Real-time monitoring and control interface
- **Portfolio Management**: Position tracking and performance analytics
- **Notification System**: Email alerts for trades and important events
- **Execution Modes**: Demo mode or live Solana execution via executor endpoint

## ⚠️ Important Disclaimer

**This software is for educational purposes only. Trading involves substantial risk of loss. Never trade with money you cannot afford to lose. The developers are not responsible for any financial losses.**

## Prerequisites

- Python 3.8 or higher
- PostgreSQL database
- Internet connection for market data
- Solana wallet/executor endpoint for live mode

## Quick Start

### 1. Clone and Setup

```bash
# Clone the repository
git clone <repository-url>
cd automated-coin-trading-bot

# Run the setup script
./scripts/setup.sh

# Windows (PowerShell/CMD)
python scripts/setup.py
```

### 2. Configure Environment

Edit the `.env` file with your settings:

```bash
# Database Configuration
DATABASE_URL=postgresql://username:password@localhost:5432/trading_bot

# Solana Execution
SOLANA_TRADING_MODE=demo
SOLANA_EXECUTOR_URL=
SOLANA_EXECUTOR_REQUIRE_AUTH=true
SOLANA_EXECUTOR_AUTH_HEADER=X-Executor-Key
SOLANA_EXECUTOR_API_KEY=
SOLANA_EXECUTOR_TIMEOUT_SECONDS=20
SOLANA_EXECUTOR_MAX_RETRIES=2
SOLANA_EXECUTOR_BACKOFF_SECONDS=0.4
SOLANA_WALLET_PUBLIC_KEY=
SOLANA_QUOTE_MINT=So11111111111111111111111111111111111111112
SOLANA_SLIPPAGE_BPS=100

# DexScreener token safety filters (optional)
DEXSCREENER_MIN_LIQUIDITY_USD=250000
DEXSCREENER_MIN_VOLUME_24H_USD=1000000
DEXSCREENER_MIN_TOKEN_AGE_HOURS=24
DEXSCREENER_REQUIRE_UNIQUE_BASE_SYMBOL=true
DEXSCREENER_BLOCKED_TOKEN_ADDRESSES=
DEXSCREENER_BLOCKED_PAIR_ADDRESSES=

# Trading Configuration
DEFAULT_CAPITAL=10000
MAX_POSITION_SIZE=0.1
STOP_LOSS_PERCENTAGE=0.05
TAKE_PROFIT_PERCENTAGE=0.15

# Email Notifications (Optional)
EMAIL_ENABLED=false
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USER=your_email@gmail.com
EMAIL_PASSWORD=your_app_password
```

### 3. Database Setup

Create a PostgreSQL database:

```sql
CREATE DATABASE trading_bot;
CREATE USER trading_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE trading_bot TO trading_user;
```

### 4. Run the Bot

```bash
# Start the trading bot
./scripts/run.sh

# Windows (PowerShell/CMD)
python scripts/run.py
```
Trading is **stopped by default** for safety. Start it from the dashboard or call `POST /api/v1/trading/start`.

### 5. Access the Dashboard

Open your browser and go to:
- **Dashboard**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs

### Platform-specific setup commands
- **Linux Mint / Linux**: `./scripts/setup.sh` then `./scripts/run.sh`
- **Windows (PowerShell/CMD)**: `python scripts/setup.py` then `python scripts/run.py`

## Features Overview

### Trading Strategies

1. **Momentum Strategy**: Identifies coins with strong upward or downward momentum
2. **Mean Reversion Strategy**: Finds overbought/oversold conditions for reversal trades
3. **Technical Analysis Strategy**: Uses multiple technical indicators (RSI, MACD, Bollinger Bands)

### Risk Management

- **Position Sizing**: Automatic calculation based on risk per trade
- **Stop Loss**: Configurable stop-loss levels
- **Take Profit**: Automatic profit-taking
- **Portfolio Risk**: Maximum risk per trade and daily loss limits
- **Correlation Limits**: Prevents over-concentration in correlated assets

### Web Dashboard

- **Real-time Monitoring**: Live portfolio and position updates
- **Performance Analytics**: P&L tracking and performance metrics
- **Trade History**: Complete trading log
- **Strategy Performance**: Individual strategy metrics
- **Risk Monitoring**: Real-time risk metrics and alerts

## Configuration

### Trading Parameters

Edit `app/core/config.py` to customize:

```python
# Trading Configuration
DEFAULT_CAPITAL = 10000.0
MAX_POSITION_SIZE = 0.1  # 10% of portfolio
STOP_LOSS_PERCENTAGE = 0.05  # 5%
TAKE_PROFIT_PERCENTAGE = 0.15  # 15%
MAX_DAILY_TRADES = 10
MIN_VOLUME = 100000

# Risk Management
MAX_PORTFOLIO_RISK = 0.02  # 2% portfolio risk per trade
CORRELATION_THRESHOLD = 0.7
MAX_SECTOR_EXPOSURE = 0.3  # 30% max exposure to any sector
```

### Supported Symbols

Default symbols in `settings.DEFAULT_SYMBOLS`:
- BTC-USD, ETH-USD, SOL-USD, XRP-USD, ADA-USD
- META, NVDA, NFLX, AMD, INTC

Add more symbols by editing the configuration.

## API Usage

### Start Trading

```bash
curl -X POST http://localhost:8000/api/v1/trading/start
```

### Get Portfolio Overview

```bash
curl http://localhost:8000/api/v1/portfolio/overview
```

### Get Market Data

```bash
curl http://localhost:8000/api/v1/market/data
```

### Get Active Positions

```bash
curl http://localhost:8000/api/v1/portfolio/positions
```

## Monitoring and Alerts

### Email Notifications

Configure email settings in `.env`:

```bash
EMAIL_ENABLED=true
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USER=your_email@gmail.com
EMAIL_PASSWORD=your_app_password
```

### Alert Types

- **Trade Executions**: Notifications when trades are executed
- **Risk Alerts**: Warnings when risk limits are exceeded
- **Performance Reports**: Daily/weekly performance summaries
- **System Alerts**: Bot status and error notifications

## Troubleshooting

### Common Issues

1. **Database Connection Error**
   - Check PostgreSQL is running
   - Verify DATABASE_URL in .env file
   - Ensure database exists and user has permissions

2. **Market Data Not Loading**
   - Check internet connection
   - Ensure `DEXSCREENER_ENABLED=true`
   - Verify `DEXSCREENER_CHAIN` and quote symbol

3. **Trading Not Starting**
   - Check all services are running
   - Verify risk limits are not exceeded
   - Check log files for errors

### Log Files

- **Application Logs**: `logs/trading_bot.log`
- **Error Logs**: Check console output
- **Database Logs**: Check PostgreSQL logs

### Performance Optimization

1. **Database Indexing**: Ensure proper indexes on frequently queried columns
2. **Data Caching**: Market data is cached for 5 minutes to reduce API calls
3. **Strategy Optimization**: Adjust strategy parameters based on live/paper performance logs

## Development

### Adding New Strategies

1. Create a new strategy class inheriting from `BaseStrategy`
2. Implement the `generate_signal` method
3. Add the strategy to `trading_engine.py`
4. Update configuration to enable the strategy

### Adding New Data Sources

1. Extend `DataService` class
2. Implement data fetching methods
3. Add data source to configuration
4. Update data combination logic

### Customizing Risk Management

1. Modify `RiskManager` class
2. Add new risk checks
3. Update risk limits configuration
4. Test with paper trading

## Security Considerations

1. **API Keys**: Never commit API keys to version control
2. **Database Security**: Use strong passwords and limit access
3. **Network Security**: Run behind firewall if exposing to internet
4. **Data Privacy**: Be mindful of sensitive financial data

## Support

For issues and questions:

1. Check the documentation
2. Review log files
3. Check GitHub issues
4. Create a new issue with detailed information

## License

This project is licensed under the MIT License - see the LICENSE file for details.

---

**Remember: This is educational software. Always test thoroughly before using with real money!**
