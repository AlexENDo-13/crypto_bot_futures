@echo off
chcp 65001 >nul
title CryptoBot v9.0 - Neural GUI
color 0B

echo ╔══════════════════════════════════════════════════════════════╗
echo ║     CryptoBot v9.0 - Neural Adaptive GUI                     ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found!
    pause
    exit /b 1
)

echo [INFO] Starting Neural GUI...
python main.py

echo.
echo [INFO] GUI closed.
pause
