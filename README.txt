CRYPTOBOT v9.0 FINAL - NEURAL ADAPTIVE TRADING SYSTEM
===========================================================

FIXES IN THIS VERSION
=====================
1. Fixed QPainter import error in main_window.py
2. Fixed QMenu import for system tray
3. Fixed all async/await coroutine warnings in GUI
4. Added Multi-Timeframe Analysis (15m + 1h)
5. All Python files syntax-checked before packaging

INSTALLATION
============
1. Extract ZIP to crypto_bot_futures folder
2. Copy strategies/ and ml/ folders from your old version
3. Run: install.bat  (or: pip install -r requirements.txt)
4. Configure API keys in Settings tab
5. Launch:
   - GUI:     run_gui.bat
   - Paper:   run.bat
   - Live:    run_live.bat

NOTE: strategies/ and ml/ folders are NOT included.
Copy them from your v7.1/v8.0 installation.
