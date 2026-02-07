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

# API Keys
ALPHA_VANTAGE_ENABLED=false
ALPHA_VANTAGE_API_KEY=your_alpha_vantage_key_here
YAHOO_FINANCE_ENABLED=true

# OKX Configuration
OKX_ENABLED=false
OKX_MARKET_DATA_ENABLED=false
OKX_TRADING_ENABLED=false
OKX_DEMO_TRADING=true
OKX_BASE_URL=https://www.okx.com
OKX_API_KEY=your_okx_api_key_here
OKX_SECRET_KEY=your_okx_secret_here
OKX_PASSPHRASE=your_okx_passphrase_here
OKX_QUOTE_CCY=USDT

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

# Security
SECRET_KEY=your_secret_key_here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

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
    alembic upgrade head || echo "⚠️ Database migrations failed. Please check your database connection."
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
