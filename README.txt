CRYPTOBOT v9.0 FINAL - NEURAL ADAPTIVE TRADING SYSTEM
===========================================================

FIXES IN THIS VERSION
=====================
1. Fixed balance sync in LIVE mode
   - update_balance() now fetches real balance from API
   - Balance syncs on start and every cycle
   - No more $10000 demo balance in LIVE mode
2. Fixed "coroutine was never awaited" warnings
   - All async calls properly wrapped in event loop
3. Fixed scanning (0 signals issue)
   - Lowered min_confidence thresholds (0.4 default)
   - Added detailed debug logging per symbol
   - More lenient regime adjustments
4. Fixed QPainter import error
5. Fixed .bat files - pure ASCII
6. All Python files syntax-checked

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

DEBUGGING
=========
If still 0 signals, check logs for:
  "SYMBOL: raw signals=N" - how many strategies found
  "SYMBOL: final signals=N" - after all filters
  "SYMBOL: insufficient data" - if data loading failed

To see more debug info, set log level to DEBUG in Settings.

NOTE: strategies/ and ml/ folders are NOT included.
Copy them from your v7.1/v8.0 installation.
