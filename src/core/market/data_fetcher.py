#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Data Fetcher — символы BTC/USDT→BTC-USDT, fetch_klines_async, volume из тикера
"""
import asyncio
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime

import pandas as pd

from src.utils.api_client import AsyncBingXClient
from src.config.settings import Settings


logger = logging.getLogger(__name__)


class DataFetcher:
    """Получение рыночных данных"""

    def __init__(self, api: AsyncBingXClient, settings: Settings):
        self.api = api
        self.settings = settings

    def _normalize_symbol(self, symbol: str) -> str:
        """Нормализация символа BTC/USDT → BTC-USDT"""
        if "/" in symbol:
            return symbol.replace("/", "-")
        return symbol

    async def fetch_klines_async(self, symbol: str, timeframe: str, limit: int = 100) -> Optional[pd.DataFrame]:
        """
        Асинхронное получение свечей (klines).
        Возвращает DataFrame с колонками: open, high, low, close, volume.
        """
        symbol = self._normalize_symbol(symbol)
        
        try:
            data = await self.api.get_klines(symbol, timeframe, limit)
            
            if not data or not isinstance(data, list):
                logger.debug(f"{symbol}: пустой ответ свечей")
                return None
            
            # BingX возвращает список списков: [timestamp, open, high, low, close, volume, ...]
            df = pd.DataFrame(data, columns=[
                "timestamp", "open", "high", "low", "close", "volume",
                "quote_volume", "taker_buy_volume", "taker_buy_quote_volume", "ignore"
            ])
            
            # Конвертация типов
            numeric_cols = ["open", "high", "low", "close", "volume"]
            for col in numeric_cols:
                df[col] = pd.to_numeric(df[col], errors="coerce")
            
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
            df.set_index("timestamp", inplace=True)
            df.dropna(subset=numeric_cols, inplace=True)
            
            if len(df) < 10:
                logger.debug(f"{symbol}: недостаточно валидных свечей ({len(df)})")
                return None
            
            logger.debug(f"{symbol}: получено {len(df)} свечей {timeframe}")
            return df
            
        except Exception as e:
            logger.exception(f"{symbol}: ошибка получения свечей: {e}")
            return None

    async def get_volume_24h(self, symbol: str) -> float:
        """Получить 24ч объём из тикера"""
        symbol = self._normalize_symbol(symbol)
        try:
            ticker = await self.api.get_ticker(symbol)
            volume = float(ticker.get("volume", 0))
            return volume
        except Exception as e:
            logger.warning(f"{symbol}: ошибка получения объёма: {e}")
            return 0.0

    async def get_current_price(self, symbol: str) -> float:
        """Получить текущую цену"""
        symbol = self._normalize_symbol(symbol)
        try:
            ticker = await self.api.get_ticker(symbol)
            price = float(ticker.get("lastPrice", 0))
            return price
        except Exception as e:
            logger.warning(f"{symbol}: ошибка получения цены: {e}")
            return 0.0

    async def fetch_multiple(self, symbols: List[str], timeframe: str, limit: int = 100) -> Dict[str, pd.DataFrame]:
        """Параллельное получение свечей для нескольких символов"""
        tasks = [self.fetch_klines_async(s, timeframe, limit) for s in symbols]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        data = {}
        for sym, result in zip(symbols, results):
            if isinstance(result, Exception):
                logger.warning(f"{sym}: ошибка загрузки: {result}")
                continue
            if result is not None:
                data[sym] = result
        
        return data
