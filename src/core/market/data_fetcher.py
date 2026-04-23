#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DataFetcher — исправленный загрузчик рыночных данных.
Кэширование, обработка ошибок, корректный расчёт индикаторов.
"""
import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import time

from src.core.logger import BotLogger
from src.core.market.indicators import compute_indicators


class DataFetcher:
    """Класс для получения рыночных данных с BingX API."""

    def __init__(self, client, logger: BotLogger, settings: dict):
        self.client = client
        self.logger = logger
        self.settings = settings
        self._klines_cache: Dict[str, tuple] = {}  # (timestamp, data)
        self._contracts_cache: Optional[List[Dict]] = None
        self._contracts_cache_time = 0
        self._cache_ttl = 60  # 60 seconds for klines
        self._contracts_cache_ttl = 300  # 5 minutes for contracts

    async def get_all_usdt_contracts(self) -> List[Dict]:
        """Получает список всех USDT-фьючерсов с кэшированием."""
        now = time.time()
        if self._contracts_cache and (now - self._contracts_cache_time) < self._contracts_cache_ttl:
            return self._contracts_cache

        try:
            result = await self.client.get_symbol_info()
            if result and result.get("code") == 0:
                contracts = []
                for c in result.get("data", []):
                    symbol = c.get("symbol", "")
                    if symbol.endswith("-USDT") and not symbol.startswith("NC"):
                        contracts.append(c)
                self._contracts_cache = contracts
                self._contracts_cache_time = now
                return contracts
        except Exception as e:
            self.logger.error(f"Ошибка получения списка контрактов: {e}")

        # Fallback: return cached or empty
        return self._contracts_cache or []

    async def fetch_klines_async(
        self, session, symbol: str, interval: str = "15m", limit: int = 100
    ) -> Optional[pd.DataFrame]:
        """Загрузка свечей с кэшированием."""
        cache_key = f"{symbol}_{interval}_{limit}"
        now = time.time()

        if cache_key in self._klines_cache:
            cache_time, cached_df = self._klines_cache[cache_key]
            if (now - cache_time) < self._cache_ttl and cached_df is not None and not cached_df.empty:
                return cached_df

        try:
            klines = await self.client.get_klines(symbol.replace("/", "-"), interval=interval, limit=limit)
            if not klines:
                return None

            df = pd.DataFrame(klines)
            if df.empty:
                return None

            # Ensure required columns
            required_cols = ["timestamp", "open", "high", "low", "close", "volume"]
            for col in required_cols:
                if col not in df.columns:
                    self.logger.warning(f"Отсутствует колонка {col} в данных {symbol}")
                    return None

            # Convert types
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
            for col in ["open", "high", "low", "close", "volume"]:
                df[col] = pd.to_numeric(df[col], errors="coerce")

            df = df.dropna()
            if len(df) < 26:
                self.logger.warning(f"Недостаточно данных {symbol}: {len(df)} свечей")
                return None

            df.sort_values("timestamp", inplace=True)
            df.reset_index(drop=True, inplace=True)

            # Cache result
            self._klines_cache[cache_key] = (now, df)
            return df

        except Exception as e:
            self.logger.error(f"Ошибка загрузки свечей {symbol}: {e}")
            return None

    def compute_indicators(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Безопасный расчёт индикаторов."""
        if df is None or df.empty or len(df) < 26:
            return {}
        try:
            return compute_indicators(df)
        except Exception as e:
            self.logger.error(f"Ошибка расчёта индикаторов: {e}")
            return {}

    async def get_ticker_data(self, symbol: str) -> Optional[Dict]:
        """Получает тикер с кэшированием."""
        try:
            return await self.client.get_ticker(symbol.replace("/", "-"))
        except Exception as e:
            self.logger.error(f"Ошибка получения тикера {symbol}: {e}")
            return None

    def clear_cache(self):
        """Очищает кэш."""
        self._klines_cache.clear()
        self._contracts_cache = None
        self._contracts_cache_time = 0
