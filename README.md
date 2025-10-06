# 🤖 Automated Stock Trading Bot **QuantFlow**

A sophisticated, fully functional automated stock trading bot with real-time data feeds, advanced trading strategies, comprehensive risk management, and a modern web dashboard.

![Python](https://img.shields.io/badge/python-v3.8+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.104.1-green.svg)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-13+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

## ✨ Features

### 🎯 Core Trading Engine
- **Multi-Strategy Framework**: Momentum, Mean Reversion, Technical Analysis, and ML-based strategies
- **Real-time Signal Generation**: Continuous market analysis and signal production
- **Automated Trade Execution**: Seamless order placement and management
- **Strategy Performance Tracking**: Individual strategy metrics and optimization

### 📊 Data Integration
- **Multiple Data Sources**: Yahoo Finance (primary) and Alpha Vantage (secondary)
- **Real-time Market Data**: Live price feeds, volume, and fundamental data
- **Technical Indicators**: RSI, MACD, Bollinger Bands, Moving Averages
- **Historical Data**: Backtesting and analysis capabilities

### 🛡️ Risk Management
- **Position Sizing**: Automatic calculation based on portfolio risk
- **Stop Loss & Take Profit**: Configurable risk controls
- **Portfolio Diversification**: Correlation and sector exposure limits
- **Daily Risk Limits**: Maximum daily loss and trade limits
- **Value at Risk (VaR)**: Portfolio risk assessment

### 💼 Portfolio Management
- **Real-time Tracking**: Live portfolio value and P&L
- **Position Management**: Open positions with unrealized P&L
- **Trade History**: Complete trading log with performance metrics
- **Performance Analytics**: Sharpe ratio, drawdown, and return analysis

### 🌐 Web Dashboard
- **Real-time Monitoring**: Live portfolio and market data updates
- **Interactive Charts**: Portfolio performance and position distribution
- **Strategy Control**: Enable/disable strategies and adjust parameters
- **Risk Monitoring**: Real-time risk metrics and alerts
- **Trade Management**: View and analyze trading history

### 🔔 Notification System
- **Email Alerts**: Trade executions, risk warnings, and performance reports
- **Custom Notifications**: Configurable alert types and priorities
- **System Status**: Bot status and error notifications
- **Performance Reports**: Daily and weekly summaries

### 🗄️ Database & API
- **PostgreSQL Integration**: Robust data persistence
- **RESTful API**: Complete API for external integrations
- **Database Migrations**: Alembic-based schema management
- **API Documentation**: Interactive Swagger/OpenAPI docs

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- PostgreSQL 13+
- Internet connection for market data

### 1. Clone and Setup
```bash
git clone https://github.com/ArliT1-F/QuantFlow
cd QuantFlow
./scripts/setup.sh
```

### 2. Configure Environment
Edit `.env` file:
```bash
# Database
DATABASE_URL=postgresql://username:password@localhost:5432/trading_bot

# API Keys (Optional)
ALPHA_VANTAGE_API_KEY=your_key_here

# Trading Configuration
DEFAULT_CAPITAL=10000
MAX_POSITION_SIZE=0.1
STOP_LOSS_PERCENTAGE=0.05
TAKE_PROFIT_PERCENTAGE=0.15

# Email Notifications (Optional)
EMAIL_ENABLED=false
EMAIL_HOST=smtp.gmail.com
EMAIL_USER=your_email@gmail.com
EMAIL_PASSWORD=your_app_password
```

### 3. Database Setup
```sql
CREATE DATABASE trading_bot;
CREATE USER trading_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE trading_bot TO trading_user;
```

### 4. Run the Bot
```bash
./scripts/run.sh
```

### 5. Access Dashboard
- **Web Dashboard**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health

## 📈 Trading Strategies

### 1. Momentum Strategy
Identifies stocks with strong upward/downward momentum using price movement and volume analysis.

**Key Features:**
- Price momentum calculation
- Volume confirmation
- RSI integration
- Trend following approach

### 2. Mean Reversion Strategy
Finds overbought/oversold conditions expecting prices to revert to their mean.

**Key Features:**
- Statistical analysis (z-scores)
- Bollinger Bands
- RSI confirmation
- Mean reversion logic

### 3. Technical Analysis Strategy
Combines multiple technical indicators for comprehensive signal generation.

**Key Features:**
- Multiple indicators (SMA, EMA, MACD, RSI, BB)
- Signal confirmation system
- Volume analysis
- Trend identification

### 4. Machine Learning Strategy
Uses Random Forest ML model to predict price movements based on multiple features.

**Key Features:**
- Feature engineering
- Random Forest classifier
- Probability-based signals
- Adaptive learning

## 🛡️ Risk Management

### Position Sizing
- Automatic calculation based on portfolio risk (default: 2% per trade)
- Maximum position size limits (default: 10% of portfolio)
- Risk-adjusted position sizing

### Risk Controls
- **Stop Loss**: Configurable stop-loss levels (default: 5%)
- **Take Profit**: Automatic profit-taking (default: 15%)
- **Daily Limits**: Maximum daily trades and losses
- **Correlation Limits**: Prevents over-concentration

### Portfolio Risk
- **VaR Calculation**: Value at Risk assessment
- **Drawdown Monitoring**: Maximum drawdown tracking
- **Sector Exposure**: Limits exposure to any single sector
- **Correlation Analysis**: Monitors position correlations

## 🌐 Web Dashboard

### Dashboard Features
- **Real-time Portfolio**: Live portfolio value and P&L
- **Active Positions**: Current positions with unrealized P&L
- **Trading History**: Complete trade log with performance
- **Strategy Performance**: Individual strategy metrics
- **Risk Monitoring**: Real-time risk metrics and alerts
- **Market Data**: Live market prices and indicators

### Control Panel
- **Start/Stop Trading**: Control the trading engine
- **Strategy Management**: Enable/disable strategies
- **Risk Settings**: Adjust risk parameters
- **Notification Testing**: Test alert system

## 📚 API Reference

### Core Endpoints
```bash
# Trading Control
POST /api/v1/trading/start
POST /api/v1/trading/stop
GET  /api/v1/trading/status

# Portfolio Management
GET  /api/v1/portfolio/overview
GET  /api/v1/portfolio/positions
GET  /api/v1/portfolio/trades

# Market Data
GET  /api/v1/market/data
GET  /api/v1/market/data/{symbol}
GET  /api/v1/market/historical/{symbol}

# Risk Management
GET  /api/v1/risk/metrics
POST /api/v1/risk/limits

# Strategies
GET  /api/v1/strategies
GET  /api/v1/strategies/{name}/performance

# Notifications
POST /api/v1/notifications/test
POST /api/v1/notifications/alert
```

### Example Usage
```python
import requests

# Get portfolio overview
response = requests.get('http://localhost:8000/api/v1/portfolio/overview')
portfolio = response.json()

# Start trading
response = requests.post('http://localhost:8000/api/v1/trading/start')
result = response.json()

# Get market data
response = requests.get('http://localhost:8000/api/v1/market/data')
market_data = response.json()
```

## ⚙️ Configuration

### Trading Parameters
```python
# app/core/config.py
DEFAULT_CAPITAL = 10000.0
MAX_POSITION_SIZE = 0.1          # 10% of portfolio
STOP_LOSS_PERCENTAGE = 0.05      # 5%
TAKE_PROFIT_PERCENTAGE = 0.15    # 15%
MAX_DAILY_TRADES = 10
MIN_VOLUME = 100000

# Risk Management
MAX_PORTFOLIO_RISK = 0.02        # 2% portfolio risk per trade
CORRELATION_THRESHOLD = 0.7
MAX_SECTOR_EXPOSURE = 0.3        # 30% max exposure to any sector
```

### Strategy Configuration
```python
# Enable/disable strategies
ENABLED_STRATEGIES = [
    "momentum",
    "mean_reversion", 
    "technical_analysis",
    "ml_strategy"
]

# Default symbols to trade
DEFAULT_SYMBOLS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "TSLA",
    "META", "NVDA", "NFLX", "AMD", "INTC"
]
```

## 📊 Performance Monitoring

### Metrics Tracked
- **Portfolio Value**: Total portfolio value and cash balance
- **P&L Analysis**: Realized and unrealized P&L
- **Return Metrics**: Total return, daily/weekly/monthly returns
- **Risk Metrics**: Sharpe ratio, maximum drawdown, VaR
- **Trade Statistics**: Win rate, average trade size, trade frequency

### Dashboard Analytics
- **Portfolio Performance Chart**: Historical portfolio value
- **Position Distribution**: Portfolio allocation by symbol
- **Strategy Performance**: Individual strategy metrics
- **Risk Metrics**: Real-time risk monitoring

## 🔔 Notifications

### Email Configuration
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

## 🛠️ Development

### Project Structure
```
automated-stock-trading-bot/
├── app/
│   ├── api/           # API routes and endpoints
│   ├── core/          # Core configuration and database
│   ├── models/        # Database models
│   ├── services/      # Business logic services
│   └── strategies/    # Trading strategies
├── alembic/           # Database migrations
├── docs/              # Documentation
├── scripts/           # Setup and utility scripts
├── static/            # Web dashboard files
├── logs/              # Application logs
└── models/            # ML model storage
```

### Adding New Strategies
1. Create strategy class inheriting from `BaseStrategy`
2. Implement `generate_signal` method
3. Add to `trading_engine.py`
4. Update configuration

### Adding New Data Sources
1. Extend `DataService` class
2. Implement data fetching methods
3. Add to configuration
4. Update data combination logic

## 🧪 Testing

### Run Tests
```bash
# Install test dependencies
pip install pytest pytest-asyncio

# Run tests
pytest tests/
```

### Test Coverage
- Unit tests for strategies
- Integration tests for services
- API endpoint tests
- Database model tests

## 📋 Troubleshooting

### Common Issues

1. **Database Connection Error**
   - Check PostgreSQL is running
   - Verify DATABASE_URL in .env
   - Ensure database exists

2. **Market Data Not Loading**
   - Check internet connection
   - Verify API keys
   - Check Yahoo Finance access

3. **Trading Not Starting**
   - Check all services are running
   - Verify risk limits
   - Check log files

### Log Files
- **Application Logs**: `logs/trading_bot.log`
- **Error Logs**: Console output
- **Database Logs**: PostgreSQL logs

## 🔒 Security

### Best Practices
- **API Keys**: Never commit to version control
- **Database Security**: Use strong passwords
- **Network Security**: Run behind firewall
- **Data Privacy**: Protect sensitive financial data

### Production Deployment
- Use environment variables for secrets
- Enable HTTPS for web interface
- Implement proper authentication
- Regular security updates

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## ⚠️ Disclaimer

**This software is for educational purposes only. Trading involves substantial risk of loss. Never trade with money you cannot afford to lose. The developers are not responsible for any financial losses.**

### Important Notes
- This is educational software, not financial advice
- Always test thoroughly before using with real money
- Past performance does not guarantee future results
- Trading involves substantial risk of loss
- Consult with financial professionals before making investment decisions

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Submit a pull request

## 📞 Support

- **Documentation**: Check the `docs/` folder
- **Issues**: Create GitHub issues for bugs
- **Discussions**: Use GitHub discussions for questions

## 🙏 Acknowledgments

- Yahoo Finance for market data
- Alpha Vantage for additional data sources
- FastAPI for the web framework
- PostgreSQL for database support
- All open-source contributors

---

**Happy Trading! 🚀📈**

*Remember: This is educational software. Always test thoroughly and trade responsibly!*