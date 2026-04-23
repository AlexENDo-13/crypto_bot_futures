"""
Модуль получения рыночных данных с BingX
Использует AsyncBingXClient для асинхронных запросов
"""
import asyncio
import time
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from src.utils.api_client import AsyncBingXClient
from src.config.settings import Settings
from src.core.logger import BotLogger


class MarketDataFetcher:
    """Класс для получения и кэширования рыночных данных"""

    def __init__(self, client: AsyncBingXClient, settings: Settings, logger: BotLogger):
        self.client = client
        self.settings = settings
        self.logger = logger
        self._klines_cache: Dict[str, pd.DataFrame] = {}
        self._ticker_cache: Dict[str, Dict] = {}
        self._last_update: Dict[str, float] = {}
        self._cache_ttl = 5  # секунд

    async def get_all_usdt_contracts(self) -> List[str]:
        """
        Получает список всех фьючерсных контрактов USDT с BingX.
        Возвращает список символов в формате 'BTC-USDT'.
        """
        try:
            contracts = await self.client.get_all_contracts()
            symbols = [
                c["symbol"] for c in contracts
                if c.get("quoteCurrency") == "USDT" and c.get("status") == 1
            ]
            self.logger.info(f"Загружено {len(symbols)} контрактов USDT")
            return symbols
        except Exception as e:
            self.logger.error(f"Исключение при получении контрактов: {e}")
            return []

    async def fetch_klines(
        self, symbol: str, interval: str = "1h", limit: int = 100
    ) -> Optional[pd.DataFrame]:
        """
        Получение исторических свечей.
        symbol в формате 'BTC-USDT', интервал: 1m,5m,15m,30m,1h,4h,1d.
        """
        cache_key = f"{symbol}_{interval}_{limit}"
        now = time.time()
        if cache_key in self._klines_cache and (now - self._last_update.get(cache_key, 0)) < self._cache_ttl:
            return self._klines_cache[cache_key]

        try:
            symbol_clean = symbol.replace(":USDT", "").replace("/", "-").upper()
            if not symbol_clean.endswith("-USDT"):
                symbol_clean = f"{symbol_clean}-USDT"
            klines = await self.client.get_klines(symbol_clean, interval, limit)
            if not klines:
                return None

            # BingX возвращает: [openTime, open, high, low, close, volume, closeTime] — 7 колонок
            df = pd.DataFrame(klines, columns=["openTime", "open", "high", "low", "close", "volume", "closeTime"])
            numeric_cols = ["open", "high", "low", "close", "volume"]
            df[numeric_cols] = df[numeric_cols].astype(float)
            df["openTime"] = pd.to_datetime(df["openTime"], unit="ms")
            df["closeTime"] = pd.to_datetime(df["closeTime"], unit="ms")
            df.set_index("openTime", inplace=True)
            df.sort_index(inplace=True)

            self._klines_cache[cache_key] = df
            self._last_update[cache_key] = now
            return df
        except Exception as e:
            self.logger.error(f"Ошибка в fetch_klines для {symbol}: {e}")
            return None

    async def fetch_ticker(self, symbol: str) -> Optional[Dict]:
        """Получение текущего тикера."""
        cache_key = f"ticker_{symbol}"
        now = time.time()
        if cache_key in self._ticker_cache and (now - self._last_update.get(cache_key, 0)) < self._cache_ttl:
            return self._ticker_cache[cache_key]

        try:
            symbol_clean = symbol.replace(":USDT", "").replace("/", "-").upper()
            if not symbol_clean.endswith("-USDT"):
                symbol_clean = f"{symbol_clean}-USDT"
            data = await self.client.get_ticker(symbol_clean)
            if data:
                # ИСПРАВЛЕНО: volume_24h берётся из quoteVolume (USDT), а не volume (BTC)
                # BingX API возвращает volume в базовой валюте и quoteVolume в USDT
                ticker = {
                    "symbol": symbol,
                    "last_price": float(data.get("lastPrice", 0)),
                    "bid": float(data.get("bidPrice", 0)),
                    "ask": float(data.get("askPrice", 0)),
                    "volume_24h": float(data.get("quoteVolume", data.get("volume", 0))),
                    "high_24h": float(data.get("highPrice", 0)),
                    "low_24h": float(data.get("lowPrice", 0)),
                    "change_percent": float(data.get("priceChangePercent", 0)),
                }
                self._ticker_cache[cache_key] = ticker
                self._last_update[cache_key] = now
                return ticker
            return None
        except Exception as e:
            self.logger.error(f"Ошибка fetch_ticker для {symbol}: {e}")
            return None

    async def fetch_order_book(self, symbol: str, limit: int = 20) -> Optional[Dict]:
        """Получение стакана заявок."""
        try:
            symbol_clean = symbol.replace(":USDT", "").replace("/", "-").upper()
            if not symbol_clean.endswith("-USDT"):
                symbol_clean = f"{symbol_clean}-USDT"
            data = await self.client.get_order_book(symbol_clean, limit)
            if data:
                return {
                    "bids": [[float(p), float(q)] for p, q in data.get("bids", [])],
                    "asks": [[float(p), float(q)] for p, q in data.get("asks", [])],
                }
            return None
        except Exception as e:
            self.logger.error(f"Ошибка fetch_order_book для {symbol}: {e}")
            return None

    async def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Добавляет технические индикаторы: SMA, EMA, RSI (Wilder), MACD,
        Bollinger Bands, ATR.
        """
        if df.empty:
            return df

        df = df.copy()
        try:
            # SMA
            df['sma_20'] = df['close'].rolling(window=20).mean()
            df['sma_50'] = df['close'].rolling(window=50).mean()

            # EMA
            df['ema_12'] = df['close'].ewm(span=12, adjust=False).mean()
            df['ema_26'] = df['close'].ewm(span=26, adjust=False).mean()

            # RSI (Wilder's smoothing)
            delta = df['close'].diff()
            gain = delta.where(delta > 0, 0.0)
            loss = (-delta.where(delta < 0, 0.0))

            # Wilder EMA: alpha = 1/period
            alpha = 1.0 / 14
            avg_gain = gain.ewm(alpha=alpha, adjust=False).mean()
            avg_loss = loss.ewm(alpha=alpha, adjust=False).mean()
            rs = avg_gain / avg_loss.replace(0, np.nan)
            df['rsi'] = 100 - (100 / (1 + rs))

            # MACD
            df['macd'] = df['ema_12'] - df['ema_26']
            df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
            df['macd_hist'] = df['macd'] - df['macd_signal']

            # Bollinger Bands
            df['bb_mid'] = df['close'].rolling(window=20).mean()
            bb_std = df['close'].rolling(window=20).std()
            df['bb_upper'] = df['bb_mid'] + (bb_std * 2)
            df['bb_lower'] = df['bb_mid'] - (bb_std * 2)

            # ATR (14)
            high_low = df['high'] - df['low']
            high_close = (df['high'] - df['close'].shift()).abs()
            low_close = (df['low'] - df['close'].shift()).abs()
            tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
            df['atr'] = tr.rolling(window=14).mean()
            df['atr_percent'] = (df['atr'] / df['close']) * 100

        except Exception as e:
            self.logger.error(f"Ошибка расчёта индикаторов: {e}")

        return df
