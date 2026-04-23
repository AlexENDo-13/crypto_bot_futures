#!/usr/bin/env python3
"""
Асинхронный сканер рынка (версия v5).
"""
import asyncio
from typing import List, Dict, Any, Optional

class MarketScanner:
    def __init__(self, data_fetcher, risk_manager, signal_evaluator, trap_detector, settings, logger):
        self.data_fetcher = data_fetcher
        self.risk_manager = risk_manager
        self.signal_evaluator = signal_evaluator
        self.trap_detector = trap_detector
        self.settings = settings
        self.logger = logger

    async def scan_async(self, contracts: list, balance: float) -> list:
        """
        Основной метод сканирования.
        """
        # 1. Выбираем топ по объёму
        top_symbols = await self._select_top_by_volume(contracts)
        self.logger.info(f"Selected top {len(top_symbols)} pairs")

        # 2. Параллельный анализ
        semaphore = asyncio.Semaphore(self.settings.get('async_concurrency', 2))
        async def analyze_with_sem(symbol):
            async with semaphore:
                return await self._analyze_pair_deep_async(symbol, balance)

        tasks = [analyze_with_sem(sym) for sym in top_symbols]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        candidates = []
        for res in results:
            if isinstance(res, Exception):
                self.logger.error(f"Scan error: {res}")
            elif res:
                candidates.append(res)

        self.logger.info(f"Scan complete: {len(candidates)} candidates")
        return candidates

    async def _select_top_by_volume(self, contracts: list, limit: int = 50) -> list:
        """
        Выбирает топ N символов по объёму за 24ч.
        """
        try:
            tickers = await self.data_fetcher.client.get_all_tickers()
        except Exception as e:
            self.logger.warning(f"Failed to fetch tickers: {e}, using all contracts")
            return [c['symbol'] for c in contracts[:limit]]

        sorted_symbols = sorted(
            tickers.items(),
            key=lambda x: float(x[1].get('volume24h', 0)),
            reverse=True
        )
        return [sym for sym, _ in sorted_symbols[:limit]]

    async def _analyze_pair_deep_async(self, symbol: str, balance: float) -> Optional[Dict[str, Any]]:
        """
        Глубокий анализ одной пары.
        """
        try:
            # Загружаем свечи 1h
            session = await self.data_fetcher.client._get_session()
            df = await self.data_fetcher.fetch_klines_async(session, symbol, '1h', 100)
            if df is None or len(df) < 50:
                return None

            indicators = self.data_fetcher.compute_indicators(df)
            if not indicators:
                return None

            # Оценка сигнала
            direction, strength, details = self.signal_evaluator.evaluate(indicators)
            if direction.value == "NEUTRAL" or strength < self.settings.get('min_signal_strength', 0.5):
                return None

            # Проверка на ловушку
            current_price = indicators['close_price']
            if self.trap_detector.is_trap(symbol, indicators, current_price):
                return None

            # Расчёт размера позиции
            risk_percent = self.settings.get('max_risk_per_trade', 2.0)
            leverage = self.settings.get('max_leverage', 3)
            stop_distance = self._calc_stop_distance(indicators)

            qty = self.risk_manager.calculate_position_size(
                symbol, balance, risk_percent, stop_distance,
                leverage, indicators.get('atr_percent', 1.0), current_price
            )

            if qty <= 0:
                return None

            return {
                'symbol': symbol,
                'direction': direction.value,
                'strength': strength,
                'qty': qty,
                'price': current_price,
                'stop_loss': current_price * (1 - stop_distance / 100.0) if direction.value == 'LONG' else current_price * (1 + stop_distance / 100.0),
                'indicators': indicators
            }
        except Exception as e:
            self.logger.error(f"Error analyzing {symbol}: {e}")
            return None

    def _calc_stop_distance(self, indicators: dict) -> float:
        atr = indicators.get('atr_percent', 1.5)
        return max(1.5, min(1.5 * atr, 8.0))
