# CryptoBot v7.1 - Professional Futures Trading Bot

## Fixed in v7.1

1. **main.py** - Added fatal error handling, graceful shutdown
2. **api_client.py** - Fixed BingX signature generation, error 100412/100001 handling, retry logic
3. **data_fetcher.py** - Fixed klines parsing (error: 0), added mock data fallback
4. **trade_executor.py** - Fixed qty calculation, volume_24h=0 validation, live/paper modes
5. **risk_manager.py** - Added update_pnl method, zero division protection
6. **market_scanner.py** - Improved error handling during scanning
7. **main_window.py** - Bot no longer crashes on startup, worker with try/except, removed useless theme button
8. **settings.py** - Added scan_interval, proper load/save
9. **notifications.py** - Fixed field names to match settings

## Installation

```bash
pip install -r requirements.txt
python main.py
```

## Structure

```
crypto_bot_futures/
├── main.py
├── requirements.txt
├── config/
│   └── settings.json
├── data/
│   ├── cache/
│   ├── state/
│   └── models/
├── logs/
└── src/
    ├── core/        # logger, settings, config, events, state, security, notifications
    ├── exchange/    # api_client, data_fetcher, market_scanner, trade_executor
    ├── risk/        # risk_manager
    ├── strategies/  # strategies
    ├── ml/          # ml_engine
    └── ui/          # main_window
```

## Important

- Default is **Paper Trading** - no real money spent
- For live trading enter BingX API keys in Settings
- Always start with paper trading for testing
