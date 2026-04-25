CryptoBot v8.0 - Professional Futures Trading Bot
============================================================

WHAT'S NEW IN v8.0
------------------

1. HEADLESS MODE (run without GUI)
   - Perfect for .bat files, servers, VPS, cron jobs
   - Command: python main.py --headless --paper --interval 60
   - Auto-trading supported in headless mode

2. .BAT LAUNCHERS (Windows)
   - run.bat        -> Headless paper trading (double-click and go)
   - run_live.bat   -> Headless LIVE trading (with confirmation)
   - run_gui.bat    -> Graphical interface
   - install.bat    -> Install all dependencies

3. PARTIAL TAKE-PROFITS
   - TP1: Close 50% of position, move SL to breakeven
   - TP2: Close remaining 30% at extended target
   - Configurable percentages

4. MARKET REGIME DETECTION
   - Detects trending / ranging / volatile markets
   - Adjusts signal confidence thresholds dynamically
   - ADX-based trend strength calculation

5. COMPOSITE SIGNAL SCORING
   - Base confidence (strategy)
   + Volatility score
   + Volume confirmation
   + Trend alignment
   = Final composite score (0-1)

6. PERFORMANCE MONITORING
   - Real-time metrics: scans, signals, trades, errors
   - Average scan time tracking
   - Export trades to CSV

7. SYSTEM TRAY SUPPORT
   - Minimize to tray
   - Tray menu: Start/Stop/Exit
   - Double-click to restore

8. AUTO-TRADE TOGGLE
   - Enable/disable automatic execution in GUI
   - Headless mode respects --auto-trade flag

9. BATCH TICKER API
   - Get all prices in one request
   - 5x faster than individual calls
   - Reduces API rate limit pressure

10. HEALTH MONITORING
    - API health status tracking
    - Automatic failure counting
    - Graceful degradation on API issues

11. FUNDING RATE CHECK
    - Prevents entries when funding rate is too high
    - Configurable threshold (default 0.1%)

12. MAX HOLD TIME
    - Auto-close positions after 4 hours
    - Prevents stuck trades

13. DARK/LIGHT THEME
    - Toggle in View menu
    - Persisted across sessions

INSTALLATION
------------
1. Extract ZIP to your project folder
2. Double-click install.bat (or run: pip install -r requirements.txt)
3. Configure API keys in config/settings.json or via GUI
4. Launch:
   - GUI:     double-click run_gui.bat
   - Paper:   double-click run.bat
   - Live:    double-click run_live.bat

COMMAND LINE OPTIONS
--------------------
  --headless          Run without GUI
  --paper             Paper trading (default)
  --live              LIVE trading (REAL MONEY!)
  --interval N        Scan interval in seconds (default: 60)
  --duration N        Max runtime in seconds (0 = infinite)
  --backtest          Run backtest mode
  --symbol SYMBOL     Symbol for backtest
  --strategy NAME     Strategy for backtest
  --start DATE        Backtest start date
  --end DATE          Backtest end date
  --initial BALANCE   Initial balance for backtest
  --log-level LEVEL   DEBUG/INFO/WARNING/ERROR

EXAMPLES
--------
  # GUI mode
  python main.py

  # Headless paper trading, 30s interval
  python main.py --headless --paper --interval 30

  # Headless live trading for 1 hour
  python main.py --headless --live --interval 60 --duration 3600

  # Backtest
  python main.py --backtest --symbol BTC-USDT --strategy ema_cross --start 2025-01-01 --end 2025-06-01

FILE STRUCTURE
--------------
  main.py                    # Entry point
  run.bat                    # Headless paper launcher
  run_live.bat               # Headless live launcher
  run_gui.bat                # GUI launcher
  install.bat                # Dependency installer
  requirements.txt           # Python packages
  src/
    exchange/
      api_client.py          # BingX API (fixed POST, batch, health)
      data_fetcher.py        # Data caching (LRU, batch prices)
      market_scanner.py      # Smart scanning (regime, composite score)
      trade_executor.py      # Execution (partial TP, breakeven SL)
    core/
      logger.py              # Logging system
      settings.py            # Configuration
      state_manager.py       # SQLite state persistence
      notifications.py       # Telegram/Discord/Email alerts
    risk/
      risk_manager.py        # Risk management
    ui/
      main_window.py         # GUI (auto-trade, performance, export)
    strategies/              # Trading strategies (unchanged)
    ml/                      # ML engine (unchanged)

NOTES
-----
- strategies/ and ml/ folders contain original files - copy them from v7.1
- Make sure config/settings.json exists before first run
- For LIVE trading, verify API keys have futures trading permissions
- Testnet recommended for initial testing

CREDITS
-------
CryptoBot v8.0 - Enhanced by community
Original: AlexENDo-13
