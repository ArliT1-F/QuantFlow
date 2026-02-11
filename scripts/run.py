import os
import sys
import subprocess
import platform
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
VENV_DIR = BASE_DIR / "scripts" / "venv"


def run_command(command, cwd=None):
    try:
        subprocess.check_call(command, cwd=cwd)
    except subprocess.CalledProcessError:
        print(f"❌ Command failed: {' '.join(command)}")
        sys.exit(1)


def get_venv_python():
    if platform.system() == "Windows":
        return VENV_DIR / "Scripts" / "python.exe"
    else:
        return VENV_DIR / "bin" / "python"


def check_venv():
    print("🔍 Checking virtual environment...")
    if not VENV_DIR.exists():
        print("❌ Virtual environment not found. Run setup.py first.")
        sys.exit(1)
    print("✅ Virtual environment found")


def check_env_file():
    print("🔍 Checking .env file...")
    if not (BASE_DIR / ".env").exists():
        print("❌ .env file not found. Run setup.py first.")
        sys.exit(1)
    print("✅ .env file found")


def check_database(python_path):
    print("🗄️ Checking database configuration...")

    check_script = """
import os
from dotenv import load_dotenv
load_dotenv()

db_url = os.getenv("DATABASE_URL", "")
if not db_url:
    print("❌ DATABASE_URL not set in .env file")
    exit(1)

print("✅ Database URL configured:", db_url)
"""

    subprocess.run([str(python_path), "-c", check_script], check=True)


def apply_migrations(python_path):
    print("🔄 Applying database migrations...")

    if not (BASE_DIR / "alembic.ini").exists():
        print("⚠️ alembic.ini not found — skipping migrations")
        return

    run_command([str(python_path), "-m", "alembic", "upgrade", "head"])
    print("✅ Migrations applied")


def start_app(python_path):
    print("\n🚀 Starting Automated Coin Trading Bot...\n")
    print("📊 Dashboard: http://localhost:8000")
    print("📚 API Docs:  http://localhost:8000/docs")
    print("\n⚠️ Press Ctrl+C to stop\n")

    run_command(
        [str(python_path), "main.py"],
        cwd=BASE_DIR
    )


def main():
    check_venv()
    check_env_file()

    python_path = get_venv_python()

    check_database(python_path)
    apply_migrations(python_path)
    start_app(python_path)


if __name__ == "__main__":
    main()