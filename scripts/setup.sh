#!/bin/bash

# Automated Coin Trading Bot Setup Script
# This script sets up the trading bot environment

set -e

echo "🚀 Setting up Automated Coin Trading Bot..."

# Check Python version
echo "📋 Checking Python version..."
python3 --version || { echo "❌ Python 3.8+ is required"; exit 1; }

# Create virtual environment
echo "📦 Creating virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Upgrade pip
echo "⬆️ Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo "📚 Installing dependencies..."
pip install -r requirements.txt

# Create necessary directories
echo "📁 Creating directories..."
mkdir -p logs
mkdir -p models
mkdir -p data
mkdir -p static

# Ensure environment file exists
echo "⚙️ Setting up environment configuration..."
if [ ! -f .env ]; then
    cat > .env << 'EOF'
# Database Configuration
DATABASE_URL=sqlite:///./trading_bot.db

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

# DexScreener (market data)
DEXSCREENER_ENABLED=true
DEXSCREENER_CHAIN=
DEXSCREENER_QUOTE_SYMBOL=USDT
DEXSCREENER_TIMEOUT_SECONDS=10
DEXSCREENER_MIN_LIQUIDITY_USD=50000
DEXSCREENER_MIN_VOLUME_24H_USD=1000000
DEXSCREENER_MIN_TOKEN_AGE_HOURS=24
DEXSCREENER_REQUIRE_UNIQUE_BASE_SYMBOL=true
DEXSCREENER_BLOCKED_TOKEN_ADDRESSES=
DEXSCREENER_BLOCKED_PAIR_ADDRESSES=

# Trading Configuration
DEFAULT_CAPITAL=10000
MAX_POSITION_SIZE=0.2
MAX_PORTFOLIO_RISK=0.02
STOP_LOSS_PERCENTAGE=0.08
TAKE_PROFIT_PERCENTAGE=0.15

# Notification Settings
EMAIL_ENABLED=false
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USER=your_email@gmail.com
EMAIL_PASSWORD=your_app_password
EMAIL_TO=your_email@gmail.com

# Security
SECRET_KEY=your_secret_key_here
API_AUTH_ENABLED=true
API_AUTH_TOKEN=change-this-token
CORS_ORIGINS=http://localhost:8000,http://127.0.0.1:8000
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Execution Controls
SIGNAL_COOLDOWN_SECONDS=900
MIN_SIGNAL_CONFIDENCE=0.55
CONFLICT_STRENGTH_RATIO=1.35
MIN_HOLD_SECONDS=900

# Logging
LOG_LEVEL=INFO
LOG_FILE=logs/trading_bot.log
EOF
    echo "📝 Created .env file. Please edit it with your configuration."
fi

# Initialize database
echo "🗄️ Initializing database..."
if command -v psql &> /dev/null; then
    echo "📊 PostgreSQL detected. Please create a database named 'trading_bot' and update .env file."
else
    echo "⚠️ PostgreSQL not found. Falling back to SQLite."
    if [ -f .env ]; then
        if grep -q "DATABASE_URL=postgresql://username:password@localhost:5432/trading_bot" .env; then
            sed -i 's|DATABASE_URL=postgresql://username:password@localhost:5432/trading_bot|DATABASE_URL=sqlite:///./trading_bot.db|' .env
            echo "📝 Updated DATABASE_URL to SQLite in .env"
        fi
    fi
fi

# Run database migrations
echo "🔄 Running database migrations..."
if [ -f alembic.ini ]; then
    venv/bin/python -m alembic upgrade head || echo "⚠️ Database migrations failed. Please check your database connection."
else
    echo "⚠️ Alembic configuration not found."
fi

# Create log file
echo "📝 Creating log file..."
touch logs/trading_bot.log

# Set permissions
echo "🔐 Setting permissions..."
chmod +x scripts/*.sh 2>/dev/null || true

echo "✅ Setup completed successfully!"
echo ""
echo "📋 Next steps:"
echo "1. Edit .env file with your API keys and database credentials"
echo "2. Create a PostgreSQL database named 'trading_bot'"
echo "3. Run: source venv/bin/activate"
echo "4. Run: python main.py"
echo "5. Open http://localhost:8000 in your browser"
echo ""
echo "⚠️ IMPORTANT: This is for educational purposes only. Trading involves substantial risk."
echo "📚 Read the documentation before using with real money."
