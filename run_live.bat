@echo off
title CryptoBot v9.0 - LIVE NEURAL MODE
color 0C

echo ==========================================
echo  CryptoBot v9.0 - LIVE TRADING
echo  REAL MONEY WARNING!
echo ==========================================
echo.
echo [!] WARNING: This will trade with REAL money!
echo [!] Make sure API keys are in config/settings.json
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found!
    pause
    exit /b 1
)

set /p confirm="Type YES to start LIVE trading: "
if /I not "%confirm%"=="YES" (
    echo [INFO] Cancelled.
    pause
    exit /b 0
)

echo.
echo [INFO] Starting LIVE Neural mode...
python main.py --headless --live --interval 60 --log-level INFO

echo.
echo [INFO] Neural system stopped.
pause
