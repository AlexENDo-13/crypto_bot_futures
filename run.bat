@echo off
chcp 65001 >nul
title CryptoBot v9.0 - Neural Headless
color 0A

echo ╔══════════════════════════════════════════════════════════════╗
echo ║     CryptoBot v9.0 - Neural Adaptive Trading System          ║
echo ║                    HEADLESS MODE                             ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found! Install Python 3.10+ and add to PATH.
    pause
    exit /b 1
)

echo [INFO] Starting NEURAL HEADLESS mode (Paper Trading)...
echo [INFO] Press Ctrl+C to stop
echo.

python main.py --headless --paper --interval 60 --log-level INFO

echo.
echo [INFO] Neural system stopped.
pause
