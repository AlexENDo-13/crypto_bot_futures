"""
CryptoBot v6.0 - Data Fetcher
Multi-timeframe data fetching with caching.
"""
import time
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime, timedelta
import json
from pathlib import Path

import pandas as pd
import numpy as np


@dataclass
class Candle:
    """Represents a single candlestick."""
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float

    @classmethod
    def from_list(cls, data: List) -> "Candle":
        return cls(
            timestamp=int(data[0]),
            open=float(data[1]),
            high=float(data[2]),
            low=float(data[3]),
            close=float(data[4]),
            volume=float(data[5])
        )


class DataFetcher:
    """Fetches and caches market data from exchange."""

    def __init__(self, api_client=None, cache_dir: str = "data/cache"):
        self.api = api_client
        self.logger = logging.getLogger("CryptoBot.Data")
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self._symbols: List[str] = []
        self._klines_cache: Dict[str, pd.DataFrame] = {}
        self._last_update: Dict[str, float] = {}

        self.logger.info("DataFetcher v6.0 initialized")

    def load_symbols(self) -> List[str]:
        """Load all available trading symbols."""
        if self.api:
            symbols_data = self.api.get_symbols()
            self._symbols = [s.get("symbol", "") for s in symbols_data if s.get("symbol")]
            self.logger.info(f"Loaded {len(self._symbols)} symbols")
        else:
            # Default symbols for testing
            self._symbols = [
                "BTC-USDT", "ETH-USDT", "SOL-USDT", "XRP-USDT", 
                "ADA-USDT", "DOGE-USDT", "AVAX-USDT", "LINK-USDT",
                "MATIC-USDT", "DOT-USDT", "LTC-USDT", "BCH-USDT",
                "UNI-USDT", "ETC-USDT", "FIL-USDT"
            ]
            self.logger.info(f"Loaded {len(self._symbols)} default symbols")

        return self._symbols

    def get_klines(self, symbol: str, timeframe: str = "15m", 
                   limit: int = 100, use_cache: bool = True) -> pd.DataFrame:
        """Get OHLCV data for a symbol."""
        cache_key = f"{symbol}_{timeframe}"

        # Check cache
        if use_cache and cache_key in self._klines_cache:
            last_update = self._last_update.get(cache_key, 0)
            if time.time() - last_update < 30:  # 30 second cache
                return self._klines_cache[cache_key]

        # Fetch from API
        if self.api:
            raw_data = self.api.get_klines(symbol, timeframe, limit)
            if raw_data:
                df = self._parse_klines(raw_data)
                self._klines_cache[cache_key] = df
                self._last_update[cache_key] = time.time()
                return df

        # Generate mock data for testing
        df = self._generate_mock_data(symbol, timeframe, limit)
        self._klines_cache[cache_key] = df
        self._last_update[cache_key] = time.time()
        return df

    def _parse_klines(self, raw_data: List[List]) -> pd.DataFrame:
        """Parse raw kline data to DataFrame."""
        candles = [Candle.from_list(d) for d in raw_data]
        df = pd.DataFrame([
            {
                "timestamp": c.timestamp,
                "open": c.open,
                "high": c.high,
                "low": c.low,
                "close": c.close,
                "volume": c.volume
            }
            for c in candles
        ])
        df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms")
        df.set_index("datetime", inplace=True)
        return df

    def _generate_mock_data(self, symbol: str, timeframe: str, 
                           limit: int) -> pd.DataFrame:
        """Generate realistic mock OHLCV data for testing."""
        np.random.seed(hash(symbol) % 2**32)

        # Base price based on symbol
        base_prices = {
            "BTC-USDT": 65000, "ETH-USDT": 3500, "SOL-USDT": 150,
            "XRP-USDT": 0.55, "ADA-USDT": 0.45, "DOGE-USDT": 0.12,
            "AVAX-USDT": 35, "LINK-USDT": 18, "MATIC-USDT": 0.65,
            "DOT-USDT": 7, "LTC-USDT": 85, "BCH-USDT": 420,
            "UNI-USDT": 9, "ETC-USDT": 28, "FIL-USDT": 5.5
        }
        base = base_prices.get(symbol, 100)

        # Generate timestamps
        now = datetime.now()
        if timeframe == "1m":
            delta = timedelta(minutes=1)
        elif timeframe == "5m":
            delta = timedelta(minutes=5)
        elif timeframe == "15m":
            delta = timedelta(minutes=15)
        elif timeframe == "1h":
            delta = timedelta(hours=1)
        elif timeframe == "4h":
            delta = timedelta(hours=4)
        else:
            delta = timedelta(hours=1)

        timestamps = [now - delta * (limit - i) for i in range(limit)]

        # Generate price series with trend and volatility
        returns = np.random.normal(0.0001, 0.015, limit)
        prices = base * np.exp(np.cumsum(returns))

        df = pd.DataFrame(index=timestamps)
        df["timestamp"] = [int(t.timestamp() * 1000) for t in timestamps]
        df["open"] = prices * (1 + np.random.normal(0, 0.002, limit))
        df["high"] = df["open"] * (1 + np.abs(np.random.normal(0, 0.008, limit)))
        df["low"] = df["open"] * (1 - np.abs(np.random.normal(0, 0.008, limit)))
        df["close"] = prices
        df["volume"] = np.random.uniform(base * 1000, base * 10000, limit)

        return df

    def get_multi_timeframe(self, symbol: str, 
                            timeframes: List[str] = None) -> Dict[str, pd.DataFrame]:
        """Get data for multiple timeframes."""
        if timeframes is None:
            timeframes = ["15m", "1h", "4h"]

        result = {}
        for tf in timeframes:
            result[tf] = self.get_klines(symbol, tf)

        return result

    def get_ticker_info(self, symbol: str) -> Dict[str, Any]:
        """Get 24h ticker information."""
        if self.api:
            data = self.api.get_ticker(symbol)
            if data.get("code") == 0:
                return data.get("data", {})

        # Mock ticker
        return {
            "symbol": symbol,
            "lastPrice": 65000.0,
            "priceChangePercent": 2.5,
            "volume": 1500000000,
            "quoteVolume": 23000000000
        }
