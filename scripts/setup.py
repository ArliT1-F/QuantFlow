import os
import sys
import subprocess
import platform
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
VENV_DIR = BASE_DIR / "venv"


def run_command(command, shell=False):
    try:
        subprocess.check_call(command, shell=shell, cwd=BASE_DIR)
    except subprocess.CalledProcessError:
        print(f"❌ Command failed: {' '.join(map(str, command))}")
        sys.exit(1)


def get_venv_paths():
    if platform.system() == "Windows":
        python_path = VENV_DIR / "Scripts" / "python.exe"
        pip_path = VENV_DIR / "Scripts" / "pip.exe"
    else:
        python_path = VENV_DIR / "bin" / "python"
        pip_path = VENV_DIR / "bin" / "pip"

    return python_path, pip_path


def check_python():
    print("📋 Checking Python version...")
    if sys.version_info < (3, 8):
        print("❌ Python 3.8+ is required")
        sys.exit(1)
    print(f"✅ Python {sys.version.split()[0]} detected")


def create_venv():
    print("📦 Creating virtual environment...")
    run_command([sys.executable, "-m", "venv", str(VENV_DIR)])


def install_dependencies(pip_path):
    print("⬆️ Upgrading pip...")
    run_command([str(pip_path), "install", "--upgrade", "pip"])

    print("📚 Installing dependencies...")
    if (BASE_DIR / "requirements.txt").exists():
        run_command([str(pip_path), "install", "-r", "requirements.txt"])
    else:
        print("⚠️ requirements.txt not found")


def create_directories():
    print("📁 Creating directories...")
    for folder in ["logs", "models", "data", "static"]:
        (BASE_DIR / folder).mkdir(exist_ok=True)


def create_env_file():
    env_file = BASE_DIR / ".env"
    if env_file.exists():
        print("⚙️ .env file already exists")
        return

    print("📝 Creating .env file...")
    env_content = """# Database Configuration
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

# Logging
LOG_LEVEL=INFO
LOG_FILE=logs/trading_bot.log
"""
    env_file.write_text(env_content)
    print("✅ .env file created. Edit it before running the bot.")


def create_log_file():
    log_file = BASE_DIR / "logs" / "trading_bot.log"
    log_file.touch(exist_ok=True)
    print("📝 Log file ready")


def run_migrations(python_path):
    print("🔄 Running database migrations...")
    if (BASE_DIR / "alembic.ini").exists():
        run_command([str(python_path), "-m", "alembic", "upgrade", "head"])
    else:
        print("⚠️ alembic.ini not found — skipping migrations")


def print_next_steps():
    print("\n✅ Setup completed successfully!\n")
    print("📋 Next steps:")
    if platform.system() == "Windows":
        print("1. Activate virtual environment:")
        print("   venv\\Scripts\\activate")
    else:
        print("1. Activate virtual environment:")
        print("   source venv/bin/activate")

    print("2. Edit .env with your API keys")
    print("3. Run: python main.py")
    print("4. Open http://localhost:8000")
    print("\n⚠️ Trading involves risk. Use responsibly.")


def main():
    print("🚀 Setting up Automated Coin Trading Bot...\n")

    check_python()
    create_venv()

    python_path, pip_path = get_venv_paths()

    install_dependencies(pip_path)
    create_directories()
    create_env_file()
    create_log_file()
    run_migrations(python_path)
    print_next_steps()


if __name__ == "__main__":
    main()
