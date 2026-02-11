@echo off
setlocal

echo 🚀 Setting up Automated Coin Trading Bot...
python scripts\setup.py
if errorlevel 1 (
  echo ❌ Setup failed.
  exit /b 1
)

echo ✅ Setup completed successfully.
