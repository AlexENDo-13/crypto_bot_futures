CRYPTOBOT v9.0 COMPLETE
=======================

FIXES IN THIS VERSION
=====================
1. FIXED API SIGNATURE - GET requests now build URL manually
   - All param values converted to strings
   - Signature computed from sorted params before URL encoding
   - GET url built manually to ensure correct order
2. Fixed empty ml_engine.py - recreated with MLEngine class
3. Fixed market_scanner - ML import is optional
4. Fixed 'NoneType' has no attribute 'paper'
5. Core init has try/except with detailed logging
6. Balance sync - fetches real balance from BingX API
7. Scanning - min_confidence=0.3, detailed logging
8. All 15 files syntax-checked

INSTALL
=======
1. Extract to crypto_bot_futures (OVERWRITE ALL)
2. pip install -r requirements.txt
3. Set API keys in Settings
4. run_gui.bat

IMPORTANT: OVERWRITE ALL FILES including api_client.py!
The signature fix is critical.
