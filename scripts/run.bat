@echo off
setlocal

echo 🤖 Starting Automated Coin Trading Bot...
python scripts\run.py
if errorlevel 1 (
  echo ❌ Run failed.
  exit /b 1
)
