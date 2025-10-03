#!/bin/bash

# Automated Stock Trading Bot Setup Script
# This script sets up the trading bot environment

set -e

echo "🚀 Setting up Automated Stock Trading Bot..."

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

# Copy environment file
echo "⚙️ Setting up environment configuration..."
if [ ! -f .env ]; then
    cp .env.example .env
    echo "📝 Created .env file from template. Please edit it with your configuration."
fi

# Initialize database
echo "🗄️ Initializing database..."
if command -v psql &> /dev/null; then
    echo "📊 PostgreSQL detected. Please create a database named 'trading_bot' and update .env file."
else
    echo "⚠️ PostgreSQL not found. Please install PostgreSQL and create a database."
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