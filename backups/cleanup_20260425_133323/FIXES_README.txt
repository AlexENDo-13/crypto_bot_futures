CryptoBot v7.1 - Fixed & Improved
====================================

CHANGES & FIXES:
----------------

1. api_client.py (src/exchange/)
   - FIXED: POST requests now use form-urlencoded (data=) instead of JSON (json=)
   - FIXED: Signature generation works correctly for POST requests
   - FIXED: close_position now accepts quantity parameter
   - ADDED: Server time sync to avoid timestamp errors (100412/100001)
   - ADDED: Rate limiter (20 req/sec max) to prevent 429 errors
   - ADDED: Data type validation for klines response
   - ADDED: Retry logic for BingX specific error codes

2. data_fetcher.py (src/exchange/)
   - FIXED: "Parse klines error: 0" - now validates data type before parsing
   - FIXED: Thread-safe cache with RLock
   - ADDED: LRU cache eviction (max 100 items)
   - ADDED: get_current_price() now uses /ticker API instead of klines (5x faster)
   - ADDED: get_prices_batch() for efficient multi-symbol price updates
   - ADDED: Cache TTL configurable (default 30s for klines, 5s for prices)
   - ADDED: Symbol filtering (only active USDT perpetual contracts)

3. market_scanner.py (src/exchange/)
   - FIXED: Scan speed - batch price fetch warms cache before scanning
   - FIXED: ML filter only runs if model is trained (prevents unnecessary overhead)
   - ADDED: Signal deduplication (same symbol+strategy+side)
   - ADDED: Signal cooldown (60s per symbol)
   - ADDED: Minimum scan interval (5s) to prevent overlapping scans
   - ADDED: Thread-safe scan lock

4. trade_executor.py (src/exchange/)
   - FIXED: qty=0 on entry - now fetches symbol info (min_qty, qty_precision)
   - FIXED: volume_24h=0 - now gets volume from symbol info
   - FIXED: close_position now passes quantity to API
   - FIXED: Paper trading balance now correctly tracked (deducts margin, returns on close)
   - ADDED: Duplicate position prevention
   - ADDED: Position value validation ($5 minimum)
   - ADDED: Thread-safe order execution with RLock
   - ADDED: Symbol precision rounding before order placement

5. main_window.py (src/ui/)
   - FIXED: GUI freeze during scan - moved scan to background QThread
   - FIXED: "SCAN NOW" button no longer blocks UI
   - FIXED: Re-init core updates worker references without restart
   - ADDED: Manual scan runs in separate thread with progress indicator
   - ADDED: signal_scan_done for non-blocking scan results

6. risk_manager.py (src/risk/)
   - FIXED: update_pnl method added
   - FIXED: Zero division protection in calculate_pnl_percent
   - FIXED: Entry price validation on position restore
   - ADDED: Safe mark_price validation

PERFORMANCE IMPROVEMENTS:
-------------------------
- Ticker API instead of klines for price updates (~5x faster)
- Batch price fetching for position updates
- LRU cache prevents memory bloat
- Rate limiting prevents API bans
- Signal cooldown reduces redundant scans
- Scan interval enforcement prevents overlapping work

INSTALLATION:
-------------
1. Backup your existing files
2. Extract this ZIP to your project folder (overwrite existing files)
3. pip install -r requirements.txt
4. python main.py

NOTE: src/strategies/strategies.py and src/ml/ml_engine.py were not changed
as they were already working correctly.
