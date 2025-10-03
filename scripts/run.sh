#!/bin/bash

# Automated Stock Trading Bot Run Script
# This script starts the trading bot

set -e

echo "🤖 Starting Automated Stock Trading Bot..."

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found. Please run setup.sh first."
    exit 1
fi

# Activate virtual environment
echo "🔌 Activating virtual environment..."
source venv/bin/activate

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "❌ .env file not found. Please run setup.sh first."
    exit 1
fi

# Check if database is accessible
echo "🗄️ Checking database connection..."
python -c "
import os
from dotenv import load_dotenv
load_dotenv()
db_url = os.getenv('DATABASE_URL', '')
if not db_url:
    print('❌ DATABASE_URL not set in .env file')
    exit(1)
print('✅ Database URL configured')
" || exit 1

# Start the application
echo "🚀 Starting trading bot..."
echo "📊 Dashboard will be available at: http://localhost:8000"
echo "📚 API documentation at: http://localhost:8000/docs"
echo ""
echo "⚠️ Press Ctrl+C to stop the bot"
echo ""

python main.py