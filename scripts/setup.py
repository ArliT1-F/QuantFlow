import sys
import subprocess
import platform
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
VENV_DIR = BASE_DIR / "venv"


def in_virtualenv():
    return sys.prefix != sys.base_prefix

def run_command(command, shell=False):
    try:
        subprocess.check_call(command, shell=shell)
    except subprocess.CalledProcessError:
        print(f"❌ Command failed: {' '.join(command)}")
        sys.exit(1)


def get_venv_paths():
    if platform.system() == "Windows":
        python_path = VENV_DIR / "Scripts" / "python.exe"
    else:
        python_path = VENV_DIR / "bin" / "python"

    return python_path


def check_python():
    print("📋 Checking Python version...")
    if sys.version_info < (3, 8):
        print("❌ Python 3.8+ is required")
        sys.exit(1)
    print(f"✅ Python {sys.version.split()[0]} detected")


def create_venv():
    if in_virtualenv():
        print("📦 Virtual environment already active — skipping creation")
        return

    if VENV_DIR.exists():
        print("📦 Virtual environment already exists")
        return

    print("📦 Creating virtual environment...")
    run_command([sys.executable, "-m", "venv", str(VENV_DIR)])



def install_dependencies(python_path):
    print("⬆️ Upgrading pip...")
    run_command([str(python_path), "-m", "pip", "install", "--upgrade", "pip"])

    print("📚 Installing dependencies...")
    if (BASE_DIR / "requirements.txt").exists():
        run_command([str(python_path), "-m", "pip", "install", "-r", "requirements.txt"])
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
DEXSCREENER_CHAIN=solana
DEXSCREENER_QUOTE_SYMBOL=SOL
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

    python_path = get_venv_paths()

    install_dependencies(python_path)
    create_directories()
    create_env_file()
    create_log_file()
    run_migrations(python_path)
    print_next_steps()


if __name__ == "__main__":
    main()
