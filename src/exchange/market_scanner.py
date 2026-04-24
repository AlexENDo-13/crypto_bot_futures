"""
CryptoBot v6.0 - Market Scanner
Multi-symbol market scanning with strategy analysis.
"""
import logging
import time
from typing import Dict, List, Optional, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd

from exchange.data_fetcher import DataFetcher
from strategies.strategies import StrategyManager, Signal
from ml.ml_engine import MLEngine


class MarketScanner:
    """Scans markets for trading opportunities."""

    def __init__(self, data_fetcher: DataFetcher = None,
                 strategy_manager: StrategyManager = None,
                 ml_engine: MLEngine = None,
                 max_workers: int = 4):
        self.data_fetcher = data_fetcher or DataFetcher()
        self.strategies = strategy_manager or StrategyManager()
        self.ml = ml_engine or MLEngine()
        self.logger = logging.getLogger("CryptoBot.Scanner")
        self.max_workers = max_workers

        self.symbols: List[str] = []
        self.scan_results: List[Dict] = []
        self.last_scan_time: float = 0

        self.logger.info(f"MarketScanner v6.0 | strategies={len(self.strategies.strategies)}")

    def load_symbols(self, count: int = 15) -> List[str]:
        """Load symbols to scan."""
        all_symbols = self.data_fetcher.load_symbols()
        self.symbols = all_symbols[:count] if len(all_symbols) > count else all_symbols
        self.logger.info(f"Loaded {len(self.symbols)} symbols for scanning")
        return self.symbols

    def scan_symbol(self, symbol: str, timeframe: str = "15m",
                   min_confidence: float = 0.5) -> List[Signal]:
        """Scan a single symbol for signals."""
        try:
            df = self.data_fetcher.get_klines(symbol, timeframe)
            if df is None or len(df) < 50:
                return []

            signals = self.strategies.analyze_all(df, symbol, min_confidence)

            # ML filtering
            filtered_signals = []
            for signal in signals:
                features = self.ml.extract_features(df)
                passed, score = self.ml.filter_signal(signal.confidence, features)
                if passed:
                    signal.confidence = score
                    filtered_signals.append(signal)

            return filtered_signals

        except Exception as e:
            self.logger.error(f"Scan error for {symbol}: {e}")
            return []

    def scan_all(self, timeframe: str = "15m", min_confidence: float = 0.5) -> List[Signal]:
        """Scan all symbols for signals."""
        if not self.symbols:
            self.load_symbols()

        self.logger.info(f"Starting scan of {len(self.symbols)} symbols...")
        all_signals = []

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(self.scan_symbol, sym, timeframe, min_confidence): sym
                for sym in self.symbols
            }

            for future in as_completed(futures):
                symbol = futures[future]
                try:
                    signals = future.result(timeout=30)
                    all_signals.extend(signals)
                    if signals:
                        self.logger.info(f"{symbol}: {len(signals)} signals found")
                except Exception as e:
                    self.logger.error(f"Scan failed for {symbol}: {e}")

        # Sort by confidence
        all_signals.sort(key=lambda s: s.confidence, reverse=True)

        self.scan_results = [
            {
                "symbol": s.symbol,
                "strategy": s.strategy,
                "type": s.type.value,
                "confidence": s.confidence,
                "price": s.price,
                "time": s.timestamp
            }
            for s in all_signals
        ]

        self.last_scan_time = time.time()
        self.logger.info(f"Scan complete | {len(all_signals)} signals found")

        return all_signals

    def get_top_signals(self, n: int = 10) -> List[Dict]:
        """Get top N signals from last scan."""
        return self.scan_results[:n]
