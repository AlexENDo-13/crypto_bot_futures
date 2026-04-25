#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DataFetcher — async market data loader with caching (FIXED)."""
import time
import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional

from src.core.market.indicators import compute_indicators

class DataFetcher:
    def __init__(self, client, logger, settings: dict):
        self.client = client
        self.logger = logger
        self.settings = settings

        self._klines_cache: Dict[str, Any] = {}
        self._ticker_cache: Dict[str, Any] = {}
        self._contracts_cache: Optional[List[dict]] = None
        self._contracts_cache_time = 0
        self._cache_ttl = settings.get("cache_ttl_seconds", 60)
        self._contracts_cache_ttl = 300
        self._fetch_failures = 0

    async def get_all_usdt_contracts(self) -> List[dict]:
        now = time.time()
        if self._contracts_cache and (now - self._contracts_cache_time) < self._contracts_cache_ttl:
            return self._contracts_cache
        try:
            result = await self.client.get_symbol_info()
            if result and result.get("code") == 0:
                contracts = [
                    c for c in result.get("data", [])
                    if c.get("symbol", "").endswith("-USDT")
                    and not c.get("symbol", "").startswith("NC")
                ]
                self._contracts_cache = contracts
                self._contracts_cache_time = now
                self._fetch_failures = 0
                return contracts
        except Exception as e:
            self._fetch_failures += 1
            self.logger.error(f"Contracts error: {e}")
        return self._contracts_cache or []

    async def fetch_klines_async(
        self, session, symbol: str, interval: str = "15m", limit: int = 100
    ) -> Optional[pd.DataFrame]:
        cache_key = f"{symbol}_{interval}_{limit}"
        now = time.time()

        if cache_key in self._klines_cache:
            ct, cdf = self._klines_cache[cache_key]
            if (now - ct) < self._cache_ttl and cdf is not None and not cdf.empty:
                return cdf

        try:
            klines = await self.client.get_klines(symbol.replace("/", "-"), interval=interval, limit=limit)
            if not klines:
                return None

            df = pd.DataFrame(klines)
            if df.empty:
                return None

            required_cols = ["timestamp", "open", "high", "low", "close", "volume"]
            for col in required_cols:
                if col not in df.columns:
                    return None

            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
            for col in ["open", "high", "low", "close", "volume"]:
                df[col] = pd.to_numeric(df[col], errors="coerce")

            df = df.dropna()
            if len(df) < 30:
                return None

            df.sort_values("timestamp", inplace=True)
            df.reset_index(drop=True, inplace=True)
            self._klines_cache[cache_key] = (now, df)
            self._fetch_failures = 0
            return df

        except Exception as e:
            self._fetch_failures += 1
            self.logger.error(f"Klines error {symbol}: {e}")
            return None

    def compute_indicators(self, df: Optional[pd.DataFrame]) -> dict:
        if df is None or df.empty or len(df) < 30:
            return {}
        try:
            return compute_indicators(df)
        except Exception as e:
            self.logger.error(f"Indicators error: {e}")
            return {}

    async def get_ticker_data(self, symbol: str) -> Optional[dict]:
        now = time.time()
        sym = symbol.replace("/", "-")

        if sym in self._ticker_cache:
            t, data = self._ticker_cache[sym]
            if (now - t) < 10:
                return data

        try:
            data = await self.client.get_ticker(sym)
            if data:
                # Normalize BingX ticker format
                normalized = {
                    "symbol": data.get("symbol", sym),
                    "lastPrice": float(data.get("lastPrice", data.get("price", 0))),
                    "bid": float(data.get("bidPrice", data.get("bid", 0))),
                    "ask": float(data.get("askPrice", data.get("ask", 0))),
                    "volume24h": float(data.get("volume", data.get("volume24h", 0))),
                    "fundingRate": float(data.get("fundingRate", 0)),
                    "high": float(data.get("highPrice", 0)),
                    "low": float(data.get("lowPrice", 0)),
                }
                self._ticker_cache[sym] = (now, normalized)
                return normalized
        except Exception as e:
            self.logger.debug(f"Ticker error {symbol}: {e}")

        cached = self._ticker_cache.get(sym)
        if cached:
            return cached[1]
        return None

    def clear_cache(self) -> None:
        self._klines_cache.clear()
        self._ticker_cache.clear()
        self._contracts_cache = None
        self._contracts_cache_time = 0

    def get_fetch_health(self) -> dict:
        return {
            "failures": self._fetch_failures,
            "klines_cache_size": len(self._klines_cache),
            "ticker_cache_size": len(self._ticker_cache),
        }
