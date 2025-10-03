# Automated Stock Trading Bot

A sophisticated, fully functional automated stock trading bot with real-time data feeds, advanced trading strategies, risk management, and a modern web dashboard.

## Features

- **Real-time Data Integration**: Multiple data providers (Alpha Vantage, Yahoo Finance)
- **Advanced Trading Strategies**: Technical analysis, momentum, mean reversion, and ML-based strategies
- **Risk Management**: Position sizing, stop-loss, take-profit, portfolio diversification
- **Web Dashboard**: Real-time monitoring, performance analytics, strategy configuration
- **Backtesting Engine**: Historical strategy validation
- **Alert System**: Email/SMS notifications for trades and alerts
- **Database Integration**: PostgreSQL for data persistence
- **API Endpoints**: RESTful API for external integrations

## Quick Start

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Set up Environment Variables**:
   ```bash
   cp .env.example .env
   # Edit .env with your API keys and database credentials
   ```

3. **Initialize Database**:
   ```bash
   alembic upgrade head
   ```

4. **Run the Application**:
   ```bash
   python main.py
   ```

5. **Access Dashboard**: Open http://localhost:8000

## Configuration

Edit `config/settings.py` to configure:
- Trading strategies
- Risk parameters
- Data providers
- Notification settings

## Disclaimer

This software is for educational purposes only. Trading involves substantial risk of loss. Use at your own risk.