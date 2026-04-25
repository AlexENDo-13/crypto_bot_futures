╔══════════════════════════════════════════════════════════════════╗
║           CRYPTOBOT v9.0 - NEURAL ADAPTIVE TRADING SYSTEM        ║
╚══════════════════════════════════════════════════════════════════╝

WHAT'S NEW IN v9.0
═══════════════════

1. FULL ASYNC ARCHITECTURE
   - aiohttp async HTTP client
   - Asyncio event loop for all operations
   - Concurrent symbol scanning with semaphore
   - Non-blocking WebSocket price streams

2. NEURAL COMPOSITE SCORING
   - 6-factor signal scoring:
     * Base strategy confidence (35%)
     * Volatility regime (15%)
     * Volume confirmation (10%)
     * Trend alignment (15%)
     * Momentum (RSI) (15%)
     * External sentiment (10%)
   - Adaptive confidence thresholds per regime

3. AUTOPILOT (SELF-ADAPTIVE)
   - Auto-adjusts risk per trade based on win rate
   - Adapts position size based on average P&L
   - Tightens/widens trailing stop based on volatility
   - Raises/lowers min confidence based on performance
   - Logs all adaptations with timestamps

4. SYSTEM MONITOR
   - Real-time health score (0-100%)
   - Cycle time tracking
   - API latency monitoring
   - Anomaly detection (slow cycles, error spikes)
   - Automatic recovery suggestions

5. CIRCUIT BREAKER
   - Protects API from cascading failures
   - Opens after 5 consecutive errors
   - Auto-recovery after 30 seconds
   - Graceful degradation

6. WEBSOCKET PRICE STREAMS
   - Real-time price updates via WebSocket
   - Bypasses REST API for price data
   - Automatic reconnection on disconnect

7. FUTURISTIC NEON GUI
   - Dark neon theme (black + neon green/purple)
   - Circular health gauge widget
   - Glowing neon buttons
   - System tray support
   - Neural network status tab
   - AutoPilot adaptation log
   - Real-time neural signal feed

8. PARTIAL TAKE-PROFITS
   - TP1: Close 50%, move SL to breakeven
   - TP2: Close 30% at extended target
   - Neural trailing stop (adaptive %)

9. HEADLESS MODE
   - Run without GUI: python main.py --headless
   - Perfect for servers/VPS
   - All features work in headless

10. MARKET REGIME DETECTION
    - Trending / Ranging / Volatile
    - ADX-based detection
    - Adjusts strategy weights per regime

INSTALLATION
════════════
1. Extract ZIP to crypto_bot_futures folder
2. Copy strategies/ and ml/ folders from your v7.1/v8.0
3. Run install.bat (or: pip install -r requirements.txt)
4. Configure API keys in config/settings.json
5. Launch:
   - GUI:     run_gui.bat
   - Paper:   run.bat
   - Live:    run_live.bat

QUICK START
═══════════
  python main.py                    # GUI mode
  python main.py --headless         # Headless paper
  python main.py --headless --live  # Headless LIVE

FILE STRUCTURE
══════════════
  main.py                    # Async entry point
  run.bat                    # Headless paper
  run_live.bat               # Headless live
  run_gui.bat                # GUI
  install.bat                # Installer
  requirements.txt           # Dependencies
  src/
    exchange/
      api_client.py          # Async BingX API + WebSocket
      data_fetcher.py        # Async cache + batch
      market_scanner.py      # Neural scoring + regime
      trade_executor.py      # Async execution + partial TP
    core/
      logger.py              # Logging system
      settings.py            # Configuration
      state_manager.py       # SQLite persistence
      notifications.py       # Alerts
      monitor.py             # Health monitoring
      autopilot.py           # Self-adaptation
    risk/
      risk_manager.py        # Risk management
    ui/
      main_window.py         # Neon futuristic GUI
    strategies/              # Copy from v7.1/v8.0
    ml/                      # Copy from v7.1/v8.0

NOTE: strategies/ and ml/ folders are NOT included.
Copy them from your previous version.

CREDITS
═══════
CryptoBot v9.0 - Neural Adaptive System
Enhanced by community | Original: AlexENDo-13
