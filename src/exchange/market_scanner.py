"""
CryptoBot v7.1 - Market Scanner
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

        self.logger.info(
            "MarketScanner v7.1 | strategies=%d",
            len(self.strategies.strategies)
        )

    def load_symbols(self, count: int = 15) -> List[str]:
        self.symbols = self.data_fetcher.load_symbols(count)
        self.logger.info("Loaded %d symbols for scanning", len(self.symbols))
        return self.symbols

    def scan_symbol(self, symbol: str, timeframe: str = "15m",
                    min_confidence: float = 0.5,
                    enabled_strategies: List[str] = None) -> List[Signal]:
        """Scan a single symbol."""
        try:
            df = self.data_fetcher.get_klines(symbol, timeframe)
            if df is None or len(df) < 50:
                self.logger.debug(
                    "%s: insufficient data (%d rows)",
                    symbol, len(df) if df is not None else 0
                )
                return []

            signals = self.strategies.analyze_all(
                df, symbol, min_confidence, enabled_strategies
            )

            # ML filtering
            filtered = []
            for signal in signals:
                try:
                    features = self.ml.extract_features(df)
                    passed, score = self.ml.filter_signal(signal.confidence, features)
                    if passed:
                        signal.confidence = score
                        filtered.append(signal)
                except Exception as e:
                    self.logger.debug("ML filter error: %s", e)
                    filtered.append(signal)

            return filtered

        except Exception as e:
            self.logger.error("Scan error for %s: %s", symbol, e)
            return []

    def scan_all(self, timeframe: str = "15m", min_confidence: float = 0.5,
                 enabled_strategies: List[str] = None) -> List[Signal]:
        if not self.symbols:
            self.load_symbols()

        self.logger.info("Scanning %d symbols on %s...", len(self.symbols), timeframe)
        all_signals = []

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(
                    self.scan_symbol, sym, timeframe, min_confidence, enabled_strategies
                ): sym
                for sym in self.symbols
            }

            for future in as_completed(futures):
                symbol = futures[future]
                try:
                    signals = future.result(timeout=30)
                    if signals:
                        all_signals.extend(signals)
                        self.logger.info("%s: %d signals", symbol, len(signals))
                except Exception as e:
                    self.logger.error("Scan failed for %s: %s", symbol, e)

        all_signals.sort(key=lambda s: s.confidence, reverse=True)

        self.scan_results = [
            {
                "symbol": s.symbol,
                "strategy": s.strategy,
                "type": s.type.value,
                "confidence": round(s.confidence, 3),
                "price": round(s.price, 4),
                "time": s.timestamp
            }
            for s in all_signals
        ]

        self.last_scan_time = time.time()
        self.logger.info("Scan complete | %d signals", len(all_signals))

        return all_signals

    def get_top_signals(self, n: int = 10) -> List[Dict]:
        return self.scan_results[:n]
