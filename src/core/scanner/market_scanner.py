#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
from typing import List, Dict
from src.core.logger import BotLogger
from src.config.settings import Settings

class MarketScanner:
    """
    Адаптивный сканер рынка.
    Сам подстраивает фильтры под волатильность, чтобы стабильно находить сделки.
    """
    def __init__(self, settings: Settings, logger: BotLogger, data_fetcher, risk_controller, strategy_engine):
        self.settings = settings
        self.logger = logger
        self.data_fetcher = data_fetcher
        self.risk_controller = risk_controller
        self.strategy_engine = strategy_engine
        
        self.empty_scans_count = 0
        # Базовые пороги
        self.current_min_adx = float(settings.get("min_adx", 15))
        self.current_min_atr = float(settings.get("min_atr_percent", 1.0))
        
    async def scan_async(self, balance: float, max_pairs: int = 100, max_asset_price_ratio: float = 0.5, ignore_session_check: bool = False) -> List[Dict]:
        self.logger.info(f"🔎 Сканирование рынка (Фильтры: ADX >= {self.current_min_adx:.1f}, ATR >= {self.current_min_atr:.2f}%)")
        
        contracts = await self.data_fetcher.get_all_usdt_contracts()
        if not contracts:
            self.logger.warning("❌ Не удалось получить список торговых пар с биржи")
            return[]

        # АВТОАДАПТАЦИЯ: если бот не может найти сделку 3 скана подряд, он слегка смягчает фильтры
        if self.empty_scans_count >= 3:
            self.current_min_adx = max(10.0, self.current_min_adx * 0.9)
            self.current_min_atr = max(0.5, self.current_min_atr * 0.9)
            self.logger.info(f"🔄 Адаптация: фильтры смягчены для поиска входа (ADX={self.current_min_adx:.1f}, ATR={self.current_min_atr:.2f}%)")
            self.empty_scans_count = 0

        candidates =[]
        import aiohttp
        async with aiohttp.ClientSession() as session:
            tasks = []
            for c in contracts[:max_pairs]:
                symbol = c.get('symbol', '').replace('-', '/')
                tasks.append(self._analyze_symbol(session, symbol))
                
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
        for res in results:
            if isinstance(res, dict) and res:
                candidates.append(res)
                
        if not candidates:
            self.empty_scans_count += 1
            self.logger.info("📭 Подходящих сигналов не найдено. Ждем рынка...")
        else:
            self.empty_scans_count = 0
            # Возвращаем фильтры к норме, если рынок "разогрелся"
            base_adx = float(self.settings.get("min_adx", 15))
            base_atr = float(self.settings.get("min_atr_percent", 1.0))
            self.current_min_adx = min(base_adx, self.current_min_adx * 1.05)
            self.current_min_atr = min(base_atr, self.current_min_atr * 1.05)

        # Сортируем кандидатов по "силе тренда" и отдаем Топ-5
        candidates.sort(key=lambda x: x['indicators'].get('adx', 0) * x['indicators'].get('atr_percent', 0), reverse=True)
        return candidates[:5]

    async def _analyze_symbol(self, session, symbol: str) -> Dict:
        """Расчет индикаторов и оценка сигнала для пары."""
        tf = self.settings.get("timeframe", "15m")
        df = await self.data_fetcher.fetch_klines_async(session, symbol, interval=tf, limit=60)
        
        if df is None or df.empty:
            return {}
            
        indicators = self.data_fetcher.compute_indicators(df)
        if not indicators:
            return {}
            
        adx = indicators.get('adx', 0)
        atr_pct = indicators.get('atr_percent', 0)
        direction = indicators.get('signal_direction', 'NEUTRAL')
        
        if direction != 'NEUTRAL':
            # Применяем текущие адаптивные пороги
            if adx >= self.current_min_adx and atr_pct >= self.current_min_atr:
                return {'symbol': symbol, 'indicators': indicators}
                
        return {}#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
from typing import List, Dict
from src.core.logger import BotLogger
from src.config.settings import Settings

class MarketScanner:
    """
    Адаптивный сканер рынка.
    Сам подстраивает фильтры под волатильность, чтобы стабильно находить сделки.
    """
    def __init__(self, settings: Settings, logger: BotLogger, data_fetcher, risk_controller, strategy_engine):
        self.settings = settings
        self.logger = logger
        self.data_fetcher = data_fetcher
        self.risk_controller = risk_controller
        self.strategy_engine = strategy_engine
        
        self.empty_scans_count = 0
        # Базовые пороги
        self.current_min_adx = float(settings.get("min_adx", 15))
        self.current_min_atr = float(settings.get("min_atr_percent", 1.0))
        
    async def scan_async(self, balance: float, max_pairs: int = 100, max_asset_price_ratio: float = 0.5, ignore_session_check: bool = False) -> List[Dict]:
        self.logger.info(f"🔎 Сканирование рынка (Фильтры: ADX >= {self.current_min_adx:.1f}, ATR >= {self.current_min_atr:.2f}%)")
        
        contracts = await self.data_fetcher.get_all_usdt_contracts()
        if not contracts:
            self.logger.warning("❌ Не удалось получить список торговых пар с биржи")
            return[]

        # АВТОАДАПТАЦИЯ: если бот не может найти сделку 3 скана подряд, он слегка смягчает фильтры
        if self.empty_scans_count >= 3:
            self.current_min_adx = max(10.0, self.current_min_adx * 0.9)
            self.current_min_atr = max(0.5, self.current_min_atr * 0.9)
            self.logger.info(f"🔄 Адаптация: фильтры смягчены для поиска входа (ADX={self.current_min_adx:.1f}, ATR={self.current_min_atr:.2f}%)")
            self.empty_scans_count = 0

        candidates =[]
        import aiohttp
        async with aiohttp.ClientSession() as session:
            tasks = []
            for c in contracts[:max_pairs]:
                symbol = c.get('symbol', '').replace('-', '/')
                tasks.append(self._analyze_symbol(session, symbol))
                
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
        for res in results:
            if isinstance(res, dict) and res:
                candidates.append(res)
                
        if not candidates:
            self.empty_scans_count += 1
            self.logger.info("📭 Подходящих сигналов не найдено. Ждем рынка...")
        else:
            self.empty_scans_count = 0
            # Возвращаем фильтры к норме, если рынок "разогрелся"
            base_adx = float(self.settings.get("min_adx", 15))
            base_atr = float(self.settings.get("min_atr_percent", 1.0))
            self.current_min_adx = min(base_adx, self.current_min_adx * 1.05)
            self.current_min_atr = min(base_atr, self.current_min_atr * 1.05)

        # Сортируем кандидатов по "силе тренда" и отдаем Топ-5
        candidates.sort(key=lambda x: x['indicators'].get('adx', 0) * x['indicators'].get('atr_percent', 0), reverse=True)
        return candidates[:5]

    async def _analyze_symbol(self, session, symbol: str) -> Dict:
        """Расчет индикаторов и оценка сигнала для пары."""
        tf = self.settings.get("timeframe", "15m")
        df = await self.data_fetcher.fetch_klines_async(session, symbol, interval=tf, limit=60)
        
        if df is None or df.empty:
            return {}
            
        indicators = self.data_fetcher.compute_indicators(df)
        if not indicators:
            return {}
            
        adx = indicators.get('adx', 0)
        atr_pct = indicators.get('atr_percent', 0)
        direction = indicators.get('signal_direction', 'NEUTRAL')
        
        if direction != 'NEUTRAL':
            # Применяем текущие адаптивные пороги
            if adx >= self.current_min_adx and atr_pct >= self.current_min_atr:
                return {'symbol': symbol, 'indicators': indicators}
                
        return {}
