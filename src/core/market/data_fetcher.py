#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import pandas as pd
from typing import Dict, Any, List, Optional
from src.core.logger import BotLogger

# Динамический импорт решает проблему кольцевой зависимости (из-за которой вылетал UI)
def _compute_indicators(df):
    try:
        from src.core.market.indicators import compute_indicators
        return compute_indicators(df)
    except ImportError:
        return {}

class DataFetcher:
    """
    Класс для получения рыночных данных с BingX API.
    Адаптирован для реальной торговли и работы без ошибок импорта.
    """
    def __init__(self, client, logger: BotLogger, settings: dict):
        self.client = client
        self.logger = logger
        self.settings = settings

    async def get_all_usdt_contracts(self) -> List[Dict]:
        """Получает список всех бессрочных фьючерсов."""
        try:
            # Нативный запрос напрямую в API BingX для надежности
            import aiohttp
            url = "https://open-api.bingx.com/openApi/swap/v2/quote/contracts"
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as resp:
                    data = await resp.json()
                    if data.get('code') == 0:
                        contracts = []
                        for c in data.get('data',[]):
                            symbol = c.get('symbol', '')
                            # Берем только USDT-фьючерсы, исключая щиткоины/акции (NC)
                            if symbol.endswith('-USDT') and not symbol.startswith('NC'):
                                contracts.append(c)
                        return contracts
            return[]
        except Exception as e:
            self.logger.error(f"Ошибка получения списка контрактов: {e}")
            return[]

    async def fetch_klines_async(self, session, symbol: str, interval: str, limit: int = 100) -> Optional[pd.DataFrame]:
        """Загрузка свечей и упаковка их в DataFrame для анализа."""
        try:
            klines = await self.client.get_klines(symbol.replace("/", "-"), interval=interval, limit=limit)
            if not klines:
                return None
                
            df = pd.DataFrame(klines)
            if df.empty:
                return None
                
            if 'time' in df.columns:
                df.rename(columns={'time': 'timestamp'}, inplace=True)
                
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            for col in ['open', 'high', 'low', 'close', 'volume']:
                if col in df.columns:
                    df[col] = df[col].astype(float)
                    
            df.sort_values('timestamp', inplace=True)
            return df
        except Exception as e:
            self.logger.error(f"Ошибка загрузки свечей {symbol}: {e}")
            return None

    def compute_indicators(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Безопасный расчет индикаторов."""
        if df is None or df.empty or len(df) < 14:
            return {}
        return _compute_indicators(df)
