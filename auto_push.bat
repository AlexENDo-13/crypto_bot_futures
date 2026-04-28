@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"
python auto_push.py
pause
