#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MarketScanner — полноценный адаптивный сканер рынка.
Фильтры по объёму, funding rate, спреду, whitelist/blacklist.
"""
import asyncio
from typing import List, Dict, Any
from datetime import datetime
import time

from src.core.logger import BotLogger
from src.config.settings import Settings


class MarketScanner:
    """Адаптивный сканер рынка с полным набором фильтров."""

    def __init__(self, settings: Settings, logger: BotLogger, data_fetcher, risk_controller, strategy_engine):
        self.settings = settings
        self.logger = logger
        self.data_fetcher = data_fetcher
        self.risk_controller = risk_controller
        self.strategy_engine = strategy_engine

        self.empty_scans_count = 0
        self.current_min_adx = float(settings.get("min_adx", 15))
        self.current_min_atr = float(settings.get("min_atr_percent", 1.0))
        self.current_min_volume = float(settings.get("min_volume_24h_usdt", 100000))
        self.current_min_signal = float(settings.get("min_signal_strength", 0.35))

        # Filters
        self.use_spread_filter = settings.get("use_spread_filter", True)
        self.max_spread_pct = float(settings.get("max_spread_percent", 0.3))
        self.max_funding_rate = float(settings.get("max_funding_rate", 0.0))
        self.use_bollinger = settings.get("use_bollinger_filter", True)
        self.use_candle_patterns = settings.get("use_candle_patterns", True)
        self.use_macd = settings.get("use_macd_indicator", True)
        self.use_ichimoku = settings.get("use_ichimoku_indicator", True)
        self.trap_detector = settings.get("trap_detector_enabled", True)
        self.predictive_entry = settings.get("predictive_entry_enabled", True)
        self.use_multi_timeframe = settings.get("use_multi_timeframe", True)

        # Lists
        self.whitelist = settings.get("symbols_whitelist", [])
        self.blacklist = settings.get("blacklist", [])

    async def scan_async(
        self,
        balance: float,
        max_pairs: int = 100,
        max_asset_price_ratio: float = 0.5,
        ignore_session_check: bool = False,
    ) -> List[Dict[str, Any]]:
        """Сканирует рынок и возвращает топ кандидатов."""
        self.logger.info(
            f"🔎 Сканирование рынка (ADX>={self.current_min_adx:.1f}, "
            f"ATR>={self.current_min_atr:.2f}%, Vol>={self.current_min_volume:,.0f})"
        )

        contracts = await self.data_fetcher.get_all_usdt_contracts()
        if not contracts:
            self.logger.warning("❌ Не удалось получить список торговых пар")
            return []

        # Auto-adaptation
        if self.empty_scans_count >= 3:
            self.current_min_adx = max(8.0, self.current_min_adx * 0.85)
            self.current_min_atr = max(0.3, self.current_min_atr * 0.85)
            self.current_min_volume = max(50000, self.current_min_volume * 0.85)
            self.current_min_signal = max(0.2, self.current_min_signal * 0.85)
            self.logger.info(
                f"🔄 Адаптация: фильтры смягчены (ADX={self.current_min_adx:.1f}, "
                f"ATR={self.current_min_atr:.2f}%, Vol={self.current_min_volume:,.0f})"
            )
            self.empty_scans_count = 0

        candidates = []
        tasks = []
        processed = 0

        for c in contracts[:max_pairs]:
            symbol = c.get("symbol", "").replace("-", "/")
            if not symbol:
                continue

            # Whitelist check
            if self.whitelist:
                if symbol.replace("/", "-") not in self.whitelist and symbol not in self.whitelist:
                    continue

            # Blacklist check
            if self.blacklist:
                if symbol.replace("/", "-") in self.blacklist or symbol in self.blacklist:
                    continue

            tasks.append(self._analyze_symbol(symbol))
            processed += 1

            # Batch processing to avoid overwhelming the API
            if len(tasks) >= 20:
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for res in results:
                    if isinstance(res, dict) and res:
                        candidates.append(res)
                tasks = []
                await asyncio.sleep(0.1)

        # Process remaining
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for res in results:
                if isinstance(res, dict) and res:
                    candidates.append(res)

        if not candidates:
            self.empty_scans_count += 1
            self.logger.info("📭 Подходящих сигналов не найдено")
        else:
            self.empty_scans_count = 0
            # Restore filters
            base_adx = float(self.settings.get("min_adx", 15))
            base_atr = float(self.settings.get("min_atr_percent", 1.0))
            base_vol = float(self.settings.get("min_volume_24h_usdt", 100000))
            base_sig = float(self.settings.get("min_signal_strength", 0.35))
            self.current_min_adx = min(base_adx, self.current_min_adx * 1.05)
            self.current_min_atr = min(base_atr, self.current_min_atr * 1.05)
            self.current_min_volume = min(base_vol, self.current_min_volume * 1.05)
            self.current_min_signal = min(base_sig, self.current_min_signal * 1.05)

        # Sort by composite score
        candidates.sort(
            key=lambda x: x["indicators"].get("signal_strength", 0)
            * x["indicators"].get("adx", 0)
            * x["indicators"].get("atr_percent", 0),
            reverse=True,
        )

        top = candidates[:5]
        if top:
            self.logger.info(f"✅ Найдено {len(candidates)} сигналов, топ-{len(top)} выбран")
        return top

    async def _analyze_symbol(self, symbol: str) -> Dict[str, Any]:
        """Анализирует одну пару."""
        tf = self.settings.get("timeframe", "15m")

        # Get ticker for volume/funding check
        ticker = await self.data_fetcher.get_ticker_data(symbol)
        if not ticker:
            return {}

        volume_24h = ticker.get("volume24h", 0)
        funding_rate = ticker.get("fundingRate", 0)
        last_price = ticker.get("lastPrice", 0)
        bid = ticker.get("bid", 0)
        ask = ticker.get("ask", 0)

        # Volume filter
        if volume_24h < self.current_min_volume:
            return {}

        # Funding rate filter
        if abs(funding_rate) > abs(self.max_funding_rate) and self.max_funding_rate != 0:
            return {}

        # Spread filter
        if self.use_spread_filter and last_price > 0 and bid > 0 and ask > 0:
            spread_pct = (ask - bid) / last_price * 100
            if spread_pct > self.max_spread_pct:
                return {}

        # Fetch candles
        df = await self.data_fetcher.fetch_klines_async(None, symbol, interval=tf, limit=80)
        if df is None or df.empty:
            return {}

        indicators = self.data_fetcher.compute_indicators(df)
        if not indicators:
            return {}

        adx = indicators.get("adx", 0)
        atr_pct = indicators.get("atr_percent", 0)
        direction = indicators.get("signal_direction", "NEUTRAL")
        signal_strength = indicators.get("signal_strength", 0)

        if direction == "NEUTRAL":
            return {}

        # Apply adaptive thresholds
        if adx < self.current_min_adx or atr_pct < self.current_min_atr:
            return {}

        if signal_strength < self.current_min_signal:
            return {}

        # Multi-timeframe confirmation
        if self.use_multi_timeframe:
            confirm = await self._check_multi_timeframe(symbol, direction)
            if not confirm:
                return {}

        # Add ticker data to indicators
        indicators["volume_24h"] = volume_24h
        indicators["funding_rate"] = funding_rate
        indicators["close_price"] = last_price
        indicators["spread_pct"] = ((ask - bid) / last_price * 100) if last_price > 0 else 0

        return {"symbol": symbol, "indicators": indicators, "ticker": ticker}

    async def _check_multi_timeframe(self, symbol: str, direction: str) -> bool:
        """Проверяет согласованность на разных таймфреймах."""
        try:
            # Check 1h timeframe
            df_1h = await self.data_fetcher.fetch_klines_async(None, symbol, interval="1h", limit=50)
            if df_1h is not None and not df_1h.empty:
                ind_1h = self.data_fetcher.compute_indicators(df_1h)
                if ind_1h:
                    dir_1h = ind_1h.get("signal_direction", "NEUTRAL")
                    if dir_1h != "NEUTRAL" and dir_1h != direction:
                        return False
            return True
        except Exception:
            return True  # Don't block on MTF errors
