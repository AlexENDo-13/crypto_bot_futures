"""
CryptoBot v9.0 - Async Data Fetcher
Features: Async cache, WebSocket price priority, adaptive TTL,
          memory pressure handling, multi-timeframe prefetch
"""
import time
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import asyncio

try:
    from collections import OrderedDict
except ImportError:
    from collections.abc import OrderedDict

@dataclass
class Candle:
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float

    @classmethod
    def from_list(cls, data: List) -> Optional["Candle"]:
        try:
            if not isinstance(data, (list, tuple)) or len(data) < 6:
                return None
            return cls(timestamp=int(data[0]), open=float(data[1]), high=float(data[2]),
                       low=float(data[3]), close=float(data[4]), volume=float(data[5]))
        except (ValueError, TypeError, IndexError):
            return None

class DataFetcher:
    """Async data fetcher with intelligent caching."""

    def __init__(self, api_client=None, cache_dir: str = "data/cache",
                 cache_ttl: int = 30, max_cache_size: int = 100):
        self.api = api_client
        self.logger = logging.getLogger("CryptoBot.Data")
        self.cache_dir = cache_dir
        self.cache_ttl = cache_ttl
        self.max_cache_size = max_cache_size
        self._symbols: List[str] = []
        self._klines_cache: OrderedDict[str, pd.DataFrame] = OrderedDict()
        self._last_update: Dict[str, float] = {}
        self._price_cache: Dict[str, tuple] = {}
        self._price_ttl = 3
        self._ticker_batch_cache: Dict[str, Dict] = {}
        self._ticker_batch_time: float = 0
        self._ticker_batch_ttl = 5
        self._lock = asyncio.Lock()
        self.logger.info("DataFetcher v9.0 initialized")

    async def load_symbols(self, count: int = 15) -> List[str]:
        if self.api and self.api.api_key:
            try:
                symbols_data = await self.api.get_symbols()
                if symbols_data:
                    self._symbols = [
                        s.get("symbol", "") for s in symbols_data
                        if s.get("symbol") and s.get("status") == "1" and "USDT" in s.get("symbol", "")
                    ]
                    self.logger.info("Loaded %d symbols from API", len(self._symbols))
                    return self._symbols[:count]
            except Exception as e:
                self.logger.warning("API symbols failed: %s", e)

        self._symbols = [
            "BTC-USDT", "ETH-USDT", "SOL-USDT", "XRP-USDT", "ADA-USDT",
            "DOGE-USDT", "AVAX-USDT", "LINK-USDT", "MATIC-USDT", "DOT-USDT",
            "LTC-USDT", "BCH-USDT", "UNI-USDT", "ETC-USDT", "FIL-USDT"
        ]
        self.logger.info("Loaded %d default symbols", len(self._symbols))
        return self._symbols[:count]

    async def get_klines(self, symbol: str, timeframe: str = "15m",
                         limit: int = 100, use_cache: bool = True) -> Optional[pd.DataFrame]:
        cache_key = "%s_%s" % (symbol, timeframe)

        async with self._lock:
            if use_cache and cache_key in self._klines_cache:
                if time.time() - self._last_update.get(cache_key, 0) < self.cache_ttl:
                    return self._klines_cache[cache_key]

        if self.api and self.api.api_key:
            try:
                raw_data = await self.api.get_klines(symbol, timeframe, limit)
                if isinstance(raw_data, list) and len(raw_data) >= 50:
                    df = self._parse_klines(raw_data)
                    if df is not None and len(df) >= 50:
                        async with self._lock:
                            self._klines_cache[cache_key] = df
                            self._last_update[cache_key] = time.time()
                            while len(self._klines_cache) > self.max_cache_size:
                                self._klines_cache.popitem(last=False)
                        return df
            except Exception as e:
                self.logger.debug("API klines failed for %s: %s", symbol, e)

        if not self.api or not self.api.api_key:
            df = self._generate_mock_data(symbol, timeframe, limit)
            if df is not None and len(df) >= 50:
                async with self._lock:
                    self._klines_cache[cache_key] = df
                    self._last_update[cache_key] = time.time()
                return df
        return None

    def _parse_klines(self, raw_data: List[List]) -> Optional[pd.DataFrame]:
        if not isinstance(raw_data, list):
            self.logger.error("Parse klines: expected list, got %s", type(raw_data).__name__)
            return None
        try:
            candles = []
            for d in raw_data:
                c = Candle.from_list(d)
                if c:
                    candles.append({"timestamp": c.timestamp, "open": c.open, "high": c.high,
                                    "low": c.low, "close": c.close, "volume": c.volume})
            if len(candles) < 50:
                self.logger.warning("Parse klines: only %d candles, need >= 50", len(candles))
                return None
            df = pd.DataFrame(candles)
            df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms")
            df.set_index("datetime", inplace=True)
            return df
        except Exception as e:
            self.logger.error("Parse klines error: %s", e)
            return None

    def _generate_mock_data(self, symbol: str, timeframe: str, limit: int) -> Optional[pd.DataFrame]:
        try:
            np.random.seed(hash(symbol) % (2**32))
            base_prices = {
                "BTC-USDT": 65000, "ETH-USDT": 3500, "SOL-USDT": 150,
                "XRP-USDT": 0.55, "ADA-USDT": 0.45, "DOGE-USDT": 0.12,
                "AVAX-USDT": 35, "LINK-USDT": 18, "MATIC-USDT": 0.65,
                "DOT-USDT": 7, "LTC-USDT": 85, "BCH-USDT": 420,
                "UNI-USDT": 9, "ETC-USDT": 28, "FIL-USDT": 5.5
            }
            base = base_prices.get(symbol, 100)
            now = datetime.now()
            deltas = {"1m": 1, "5m": 5, "15m": 15, "1h": 60, "4h": 240, "1d": 1440}
            minutes = deltas.get(timeframe, 15)
            timestamps = [now - timedelta(minutes=minutes * (limit - i)) for i in range(limit)]
            returns = np.random.normal(0.0001, 0.015, limit)
            trend = np.sin(np.linspace(0, 4 * np.pi, limit)) * 0.005
            prices = base * np.exp(np.cumsum(returns + trend))
            df = pd.DataFrame(index=timestamps)
            df["timestamp"] = [int(t.timestamp() * 1000) for t in timestamps]
            df["open"] = prices * (1 + np.random.normal(0, 0.002, limit))
            df["close"] = prices
            df["high"] = np.maximum(df["open"], df["close"]) * (1 + np.abs(np.random.normal(0, 0.008, limit)))
            df["low"] = np.minimum(df["open"], df["close"]) * (1 - np.abs(np.random.normal(0, 0.008, limit)))
            df["volume"] = np.random.uniform(base * 1000, base * 10000, limit)
            df["high"] = df[["high", "open", "close"]].max(axis=1)
            df["low"] = df[["low", "open", "close"]].min(axis=1)
            return df
        except Exception as e:
            self.logger.error("Mock data error: %s", e)
            return None

    async def get_multi_timeframe(self, symbol: str, timeframes: List[str] = None) -> Dict[str, pd.DataFrame]:
        if timeframes is None:
            timeframes = ["15m", "1h", "4h"]
        tasks = [self.get_klines(symbol, tf) for tf in timeframes]
        results = await asyncio.gather(*tasks)
        return {tf: df for tf, df in zip(timeframes, results) if df is not None}

    async def get_current_price(self, symbol: str) -> float:
        now = time.time()

        # 1. WebSocket price (fastest)
        if self.api and self.api._ws_connected and symbol in self.api._ws_prices:
            return self.api._ws_prices[symbol]

        # 2. Cached price
        async with self._lock:
            cached = self._price_cache.get(symbol)
            if cached and (now - cached[1]) < self._price_ttl:
                return cached[0]

        # 3. Ticker API
        if self.api and self.api.api_key:
            try:
                resp = await self.api.get_ticker(symbol)
                if resp.get("code") == 0:
                    data = resp.get("data", {})
                    price = float(data.get("lastPrice", data.get("price", 0)))
                    if price > 0:
                        async with self._lock:
                            self._price_cache[symbol] = (price, now)
                        return price
            except Exception as e:
                self.logger.debug("Ticker failed for %s: %s", symbol, e)

        # 4. Fallback to klines
        df = await self.get_klines(symbol, "1m", 5)
        if df is not None and len(df) > 0:
            price = float(df["close"].iloc[-1])
            async with self._lock:
                self._price_cache[symbol] = (price, now)
            return price
        return 0.0

    async def get_prices_batch(self, symbols: List[str]) -> Dict[str, float]:
        result = {}
        now = time.time()

        # Try batch ticker first
        if self.api and self.api.api_key and len(symbols) > 3:
            try:
                if now - self._ticker_batch_time > self._ticker_batch_ttl:
                    batch = await self.api.get_tickers_batch()
                    if batch:
                        async with self._lock:
                            self._ticker_batch_cache = batch
                            self._ticker_batch_time = now
                async with self._lock:
                    for sym in symbols:
                        tick = self._ticker_batch_cache.get(sym)
                        if tick:
                            price = float(tick.get("lastPrice", tick.get("price", 0)))
                            if price > 0:
                                result[sym] = price
                                self._price_cache[sym] = (price, now)
                if len(result) == len(symbols):
                    return result
            except Exception as e:
                self.logger.debug("Batch ticker failed: %s", e)

        # Fallback to individual async calls
        tasks = []
        for sym in symbols:
            if sym not in result:
                tasks.append(self.get_current_price(sym))
        prices = await asyncio.gather(*tasks)
        for sym, price in zip([s for s in symbols if s not in result], prices):
            if price > 0:
                result[sym] = price
        return result
