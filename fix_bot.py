#!/usr/bin/env python3
"""
Auto-fix script for CryptoBot v9.1
Fixes: imports, size/stepSize, tradeMinUSDT, RLock, timeouts
Run: python fix_bot.py
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).parent

def read_file(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        print(f"  Cannot read {path}: {e}")
        return None

def write_file(path, content):
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"  Fixed: {path}")
        return True
    except Exception as e:
        print(f"  Cannot write {path}: {e}")
        return False

def fix_market_scanner():
    path = ROOT / "src" / "core" / "scanner" / "market_scanner.py"
    text = read_file(path)
    if text is None:
        return False

    if "from src.utils.config import Config" in text:
        text = text.replace("from src.utils.config import Config\n", "")
        print("  Removed broken import: src.utils.config")

    if 'symbol_specs.get("stepSize"' in text:
        text = text.replace('symbol_specs.get("stepSize"', 'symbol_specs.get("size", symbol_specs.get("stepSize"')
        print("  Fixed stepSize -> size")

    return write_file(path, text)

def fix_trading_engine():
    path = ROOT / "src" / "core" / "engine" / "trading_engine.py"
    text = read_file(path)
    if text is None:
        return False

    if "self._lock = threading.Lock()" in text:
        text = text.replace("self._lock = threading.Lock()", "self._lock = threading.RLock()")
        print("  Changed threading.Lock() -> threading.RLock()")

    if "get_tickers_batch" in text:
        text = text.replace("get_tickers_batch", "get_ticker")
        print("  Changed get_tickers_batch -> get_ticker")

    return write_file(path, text)

def fix_trade_executor():
    path = ROOT / "src" / "core" / "executor" / "trade_executor.py"
    text = read_file(path)
    if text is None:
        return False

    if 'symbol_specs.get("stepSize"' in text:
        text = text.replace('symbol_specs.get("stepSize"', 'symbol_specs.get("size", symbol_specs.get("stepSize"')
        print("  Fixed stepSize -> size")

    if 'symbol_specs.get("minNotional"' in text:
        text = text.replace('symbol_specs.get("minNotional"', 'symbol_specs.get("tradeMinUSDT", symbol_specs.get("minNotional"')
        print("  Fixed minNotional -> tradeMinUSDT")

    return write_file(path, text)

def fix_risk_manager():
    path = ROOT / "src" / "core" / "risk" / "risk_manager.py"
    text = read_file(path)
    if text is None:
        return False

    if 'symbol_specs.get("stepSize"' in text:
        text = text.replace('symbol_specs.get("stepSize"', 'symbol_specs.get("size", symbol_specs.get("stepSize"')
        print("  Fixed stepSize -> size")

    if 'symbol_specs.get("minNotional"' in text:
        text = text.replace('symbol_specs.get("minNotional"', 'symbol_specs.get("tradeMinUSDT", symbol_specs.get("minNotional"')
        print("  Fixed minNotional -> tradeMinUSDT")

    return write_file(path, text)

def fix_data_fetcher():
    path = ROOT / "src" / "core" / "market" / "data_fetcher.py"
    text = read_file(path)
    if text is None:
        return False

    if "isinstance(data, list)" not in text:
        old_block = 'data = await self.client.get_ticker(sym)\n            if not data:\n                return None'
        new_block = 'data = await self.client.get_ticker(sym)\n            if not data:\n                return None\n            if isinstance(data, list):\n                if len(data) == 0:\n                    return None\n                data = data[0]\n            if not isinstance(data, dict):\n                return None'
        if old_block in text:
            text = text.replace(old_block, new_block)
            print("  Added list protection in get_ticker_data")
        else:
            print("  get_ticker_data block not found (may already be fixed)")

    return write_file(path, text)

def fix_main_window():
    path = ROOT / "src" / "ui" / "main_window.py"
    text = read_file(path)
    if text is None:
        return False

    if "asyncio.wait_for(self.engine._scan_and_trade(), timeout=60)" not in text:
        if "await self.engine._scan_and_trade()" in text:
            text = text.replace(
                "await self.engine._scan_and_trade()",
                "await asyncio.wait_for(self.engine._scan_and_trade(), timeout=60)"
            )
            print("  Added timeout to run_scan (60s)")

    if "asyncio.wait_for(self.engine.start(), timeout=30)" not in text:
        if "await self.engine.start()" in text:
            text = text.replace(
                "await self.engine.start()",
                "await asyncio.wait_for(self.engine.start(), timeout=30)"
            )
            print("  Added timeout to engine start (30s)")

    if "asyncio.wait_for(self.engine.stop(), timeout=30)" not in text:
        if "await self.engine.stop()" in text:
            text = text.replace(
                "await self.engine.stop()",
                "await asyncio.wait_for(self.engine.stop(), timeout=30)"
            )
            print("  Added timeout to engine stop (30s)")

    return write_file(path, text)

def main():
    print("=" * 50)
    print("CryptoBot v9.1 Auto-Fix Script")
    print("=" * 50)
    print(f"Project root: {ROOT}")
    print()

    fixes = [
        ("Market Scanner", fix_market_scanner),
        ("Trading Engine", fix_trading_engine),
        ("Trade Executor", fix_trade_executor),
        ("Risk Manager", fix_risk_manager),
        ("Data Fetcher", fix_data_fetcher),
        ("Main Window", fix_main_window),
    ]

    for name, fix_func in fixes:
        print(f"\n{name}:")
        try:
            fix_func()
        except Exception as e:
            print(f"  Error: {e}")

    print("\n" + "=" * 50)
    print("Done! Now run: python main.py")
    print("=" * 50)

if __name__ == "__main__":
    main()
