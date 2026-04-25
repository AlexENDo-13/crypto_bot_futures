CRYPTOBOT v9.0 - NEURAL ADAPTIVE TRADING SYSTEM
============================================================

FIXES IN THIS VERSION
=====================
1. Fixed SyntaxError in trade_executor.py (Else: -> else:)
2. Fixed all case-sensitive keyword errors (For, Self, etc.)
3. Fixed .bat files - removed UTF-8 box-drawing chars, pure ASCII
4. All Python files syntax-checked before packaging
5. Fixed async/await consistency across all modules

INSTALLATION
============
1. Extract ZIP to crypto_bot_futures folder
2. Copy strategies/ and ml/ folders from your old version
3. Run: install.bat  (or: pip install -r requirements.txt)
4. Configure API keys in Settings tab or config/settings.json
5. Launch:
   - GUI:     run_gui.bat
   - Paper:   run.bat
   - Live:    run_live.bat

QUICK START
===========
  python main.py                    # GUI mode
  python main.py --headless         # Headless paper
  python main.py --headless --live  # Headless LIVE

NOTE: strategies/ and ml/ folders are NOT included.
Copy them from your v7.1/v8.0 installation.

CREDITS
=======
CryptoBot v9.0 - Neural Adaptive System
Original: AlexENDo-13
