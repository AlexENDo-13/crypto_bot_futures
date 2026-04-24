@echo off
chcp 65001 >nul
title CryptoBot v9.0 - Installation
color 0E

echo ╔══════════════════════════════════════════════════════════════╗
echo ║        CryptoBot v9.0 - Neural System Installer              ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found! Download from https://python.org
    pause
    exit /b 1
)

echo [INFO] Upgrading pip...
python -m pip install --upgrade pip

echo [INFO] Installing requirements...
pip install -r requirements.txt

echo.
echo [INFO] Creating directories...
python -c "import os; [os.makedirs(d, exist_ok=True) for d in ['logs','data/state','data/cache','config','backtests','data/trades','data/models']]"

echo.
echo [OK] Installation complete!
echo.
echo Available launchers:
echo   run.bat       - Headless paper trading
echo   run_live.bat  - Headless LIVE trading (REAL MONEY!)
echo   run_gui.bat   - Neural GUI
echo.
pause
