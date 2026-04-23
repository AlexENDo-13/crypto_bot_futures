#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MarketScanner — полноценный адаптивный сканер с мультитаймфреймом.
"""
import asyncio
from typing import List, Dict, Any
from datetime import datetime
import time

from src.core.logger import BotLogger
from src.config.settings import Settings


class MarketScanner:
    """Адаптивный сканер рынка с полным набором фильтров, MTF и логированием."""

    def __init__(self, settings: Settings, logger: BotLogger, data_fetcher, risk_controller, strategy_engine):
        self.settings = settings
        self.logger = logger
        self.data_fetcher = data_fetcher
        self.risk_controller = risk_controller
        self.strategy_engine = strategy_engine

        self.empty_scans_count = 0
        self.current_min_adx = float(settings.get("min_adx", 10))
        self.current_min_atr = float(settings.get("min_atr_percent", 0.5))
        self.current_min_volume = float(settings.get("min_volume_24h_usdt", 50000))
        self.current_min_signal = float(settings.get("min_signal_strength", 0.25))

        self.use_spread_filter = settings.get("use_spread_filter", True)
        self.max_spread_pct = float(settings.get("max_spread_percent", 0.5))
        self.max_funding_rate = float(settings.get("max_funding_rate", 0.0))
        self.use_bollinger = settings.get("use_bollinger_filter", True)
        self.use_candle_patterns = settings.get("use_candle_patterns", True)
        self.use_macd = settings.get("use_macd_indicator", True)
        self.use_ichimoku = settings.get("use_ichimoku_indicator", True)
        self.trap_detector = settings.get("trap_detector_enabled", True)
        self.predictive_entry = settings.get("predictive_entry_enabled", True)
        self.use_multi_timeframe = settings.get("use_multi_timeframe", True)
        self.mtf_timeframes = settings.get("mtf_timeframes", ["1h", "4h"])
        self.mtf_required = int(settings.get("mtf_required_agreement", 2))

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
            f"🔎 Сканирование рынка (баланс: ${balance:.2f}, "
            f"ADX>={self.current_min_adx:.1f}, ATR>={self.current_min_atr:.2f}%, "
            f"Vol>={self.current_min_volume:,.0f}, Signal>={self.current_min_signal:.2f}, "
            f"MTF={'ON' if self.use_multi_timeframe else 'OFF'})"
        )

        contracts = await self.data_fetcher.get_all_usdt_contracts()
        if not contracts:
            self.logger.error("❌ Не удалось получить список торговых пар")
            return []

        self.logger.info(f"📋 Получено {len(contracts)} контрактов с биржи")

        # Auto-adaptation after empty scans
        if self.empty_scans_count >= 2:
            old_adx = self.current_min_adx
            old_atr = self.current_min_atr
            old_vol = self.current_min_volume
            old_sig = self.current_min_signal
            self.current_min_adx = max(5.0, self.current_min_adx * 0.85)
            self.current_min_atr = max(0.1, self.current_min_atr * 0.85)
            self.current_min_volume = max(10000, self.current_min_volume * 0.85)
            self.current_min_signal = max(0.1, self.current_min_signal * 0.85)
            self.logger.info(
                f"🔄 Адаптация (пустых сканов: {self.empty_scans_count}): "
                f"ADX {old_adx:.1f}→{self.current_min_adx:.1f}, "
                f"ATR {old_atr:.2f}%→{self.current_min_atr:.2f}%, "
                f"Vol {old_vol:,.0f}→{self.current_min_volume:,.0f}, "
                f"Signal {old_sig:.2f}→{self.current_min_signal:.2f}"
            )
            self.empty_scans_count = 0

        candidates = []
        filtered_count = {
            "total": 0, "whitelist": 0, "blacklist": 0, "ticker_fail": 0,
            "volume": 0, "funding": 0, "spread": 0, "klines_fail": 0,
            "indicators_fail": 0, "neutral": 0, "adx": 0, "atr": 0,
            "signal": 0, "mtf_reject": 0, "passed": 0
        }

        # Process in batches
        batch_size = 15
        for i in range(0, min(len(contracts), max_pairs), batch_size):
            batch = contracts[i:i+batch_size]
            tasks = []
            for c in batch:
                symbol = c.get("symbol", "").replace("-", "/")
                if not symbol:
                    continue
                filtered_count["total"] += 1

                if self.whitelist:
                    clean_sym = symbol.replace("/", "-")
                    if clean_sym not in self.whitelist and symbol not in self.whitelist:
                        filtered_count["whitelist"] += 1
                        continue

                if self.blacklist:
                    clean_sym = symbol.replace("/", "-")
                    if clean_sym in self.blacklist or symbol in self.blacklist:
                        filtered_count["blacklist"] += 1
                        continue

                tasks.append(self._analyze_symbol(symbol, filtered_count))

            if tasks:
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for res in results:
                    if isinstance(res, dict) and res:
                        candidates.append(res)

            await asyncio.sleep(0.05)

        self.logger.info(
            f"📊 Фильтрация: всего={filtered_count['total']}, "
            f"wl={filtered_count['whitelist']}, bl={filtered_count['blacklist']}, "
            f"ticker={filtered_count['ticker_fail']}, vol={filtered_count['volume']}, "
            f"fund={filtered_count['funding']}, spread={filtered_count['spread']}, "
            f"klines={filtered_count['klines_fail']}, ind={filtered_count['indicators_fail']}, "
            f"neutral={filtered_count['neutral']}, adx={filtered_count['adx']}, atr={filtered_count['atr']}, "
            f"signal={filtered_count['signal']}, mtf={filtered_count['mtf_reject']}, passed={filtered_count['passed']}"
        )

        if not candidates:
            self.empty_scans_count += 1
            self.logger.info(f"📭 Сигналов не найдено (пустых сканов подряд: {self.empty_scans_count})")
        else:
            self.empty_scans_count = 0
            # Tighten filters back
            base_adx = float(self.settings.get("min_adx", 10))
            base_atr = float(self.settings.get("min_atr_percent", 0.5))
            base_vol = float(self.settings.get("min_volume_24h_usdt", 50000))
            base_sig = float(self.settings.get("min_signal_strength", 0.25))
            self.current_min_adx = min(base_adx, self.current_min_adx * 1.05)
            self.current_min_atr = min(base_atr, self.current_min_atr * 1.05)
            self.current_min_volume = min(base_vol, self.current_min_volume * 1.05)
            self.current_min_signal = min(base_sig, self.current_min_signal * 1.05)

        candidates.sort(
            key=lambda x: x["indicators"].get("signal_strength", 0)
            * x["indicators"].get("adx", 0)
            * x["indicators"].get("atr_percent", 0),
            reverse=True,
        )

        top = candidates[:5]
        if top:
            self.logger.info(f"✅ Найдено {len(candidates)} сигналов, топ-{len(top)} выбран")
            for i, c in enumerate(top[:3], 1):
                ind = c["indicators"]
                self.logger.info(
                    f"   #{i} {c['symbol']}: {ind.get('signal_direction')} [{ind.get('market_regime')}] | "
                    f"ADX={ind.get('adx', 0):.1f} | ATR={ind.get('atr_percent', 0):.2f}% | "
                    f"Signal={ind.get('signal_strength', 0):.2f} | RSI={ind.get('rsi', 0):.1f} | "
                    f"Type={ind.get('entry_type', 'unknown')}"
                )
        return top

    async def _analyze_symbol(self, symbol: str, filtered_count: dict) -> Dict[str, Any]:
        """Анализирует одну пару с MTF."""
        tf = self.settings.get("timeframe", "15m")

        # Get ticker
        ticker = await self.data_fetcher.get_ticker_data(symbol)
        if not ticker:
            filtered_count["ticker_fail"] += 1
            return {}

        volume_24h = ticker.get("volume24h", 0)
        funding_rate = ticker.get("fundingRate", 0)
        last_price = ticker.get("lastPrice", 0)
        bid = ticker.get("bid", 0)
        ask = ticker.get("ask", 0)

        # Volume filter
        if volume_24h < self.current_min_volume:
            filtered_count["volume"] += 1
            return {}

        # Funding filter
        if abs(funding_rate) > abs(self.max_funding_rate) and self.max_funding_rate != 0:
            filtered_count["funding"] += 1
            return {}

        # Spread filter
        if self.use_spread_filter and last_price > 0 and bid > 0 and ask > 0:
            spread_pct = (ask - bid) / last_price * 100
            if spread_pct > self.max_spread_pct:
                filtered_count["spread"] += 1
                return {}

        # Fetch primary candles
        df = await self.data_fetcher.fetch_klines_async(None, symbol, interval=tf, limit=80)
        if df is None or df.empty:
            filtered_count["klines_fail"] += 1
            return {}

        indicators = self.data_fetcher.compute_indicators(df)
        if not indicators:
            filtered_count["indicators_fail"] += 1
            return {}

        adx = indicators.get("adx", 0)
        atr_pct = indicators.get("atr_percent", 0)
        direction = indicators.get("signal_direction", "NEUTRAL")
        signal_strength = indicators.get("signal_strength", 0)
        rsi = indicators.get("rsi", 0)
        regime = indicators.get("market_regime", "UNKNOWN")
        entry_type = indicators.get("entry_type", "none")

        # Log regime for debugging
        self.logger.debug(
            f"📈 {symbol}: regime={regime}, dir={direction}, ADX={adx:.1f}, "
            f"ATR={atr_pct:.2f}%, RSI={rsi:.1f}, strength={signal_strength:.2f}, type={entry_type}"
        )

        if direction == "NEUTRAL":
            filtered_count["neutral"] += 1
            self.logger.debug(f"⛔ {symbol}: NEUTRAL (regime={regime}, conditions={indicators.get('signal_conditions', [])})")
            return {}

        # Threshold filters
        if adx < self.current_min_adx:
            filtered_count["adx"] += 1
            self.logger.debug(f"⛔ {symbol}: ADX {adx:.1f} < {self.current_min_adx:.1f}")
            return {}

        if atr_pct < self.current_min_atr:
            filtered_count["atr"] += 1
            self.logger.debug(f"⛔ {symbol}: ATR {atr_pct:.2f}% < {self.current_min_atr:.2f}%")
            return {}

        if signal_strength < self.current_min_signal:
            filtered_count["signal"] += 1
            self.logger.debug(f"⛔ {symbol}: signal {signal_strength:.2f} < {self.current_min_signal:.2f}")
            return {}

        # Multi-timeframe analysis
        if self.use_multi_timeframe:
            mtf_result = await self._check_multi_timeframe(symbol, direction)
            if not mtf_result["agreement"]:
                filtered_count["mtf_reject"] += 1
                self.logger.debug(
                    f"⛔ {symbol}: MTF отклонён (agree={mtf_result['agree_count']}/"
                    f"{mtf_result['total']}, need={self.mtf_required}, details={mtf_result['details']})"
                )
                return {}
            indicators["mtf_agreement"] = mtf_result["agree_count"]
            indicators["mtf_total"] = mtf_result["total"]
            self.logger.debug(
                f"✅ {symbol}: MTF подтверждён {mtf_result['agree_count']}/{mtf_result['total']}"
            )

        # Add ticker data
        indicators["volume_24h"] = volume_24h
        indicators["funding_rate"] = funding_rate
        indicators["close_price"] = last_price
        indicators["spread_pct"] = ((ask - bid) / last_price * 100) if last_price > 0 else 0

        filtered_count["passed"] += 1
        self.logger.info(
            f"✅ {symbol}: СИГНАЛ {direction} [{regime}] | ADX={adx:.1f} | ATR={atr_pct:.2f}% | "
            f"Signal={signal_strength:.2f} | RSI={rsi:.1f} | Vol={volume_24h:,.0f} | Type={entry_type}"
        )
        return {"symbol": symbol, "indicators": indicators, "ticker": ticker}

    async def _check_multi_timeframe(self, symbol: str, primary_direction: str) -> dict:
        """Полноценный мультитаймфрейм анализ."""
        agree_count = 0
        total = 0
        details = {}

        for tf in self.mtf_timeframes:
            try:
                df_tf = await self.data_fetcher.fetch_klines_async(None, symbol, interval=tf, limit=50)
                if df_tf is None or df_tf.empty:
                    details[tf] = "no_data"
                    continue

                ind_tf = self.data_fetcher.compute_indicators(df_tf)
                if not ind_tf:
                    details[tf] = "no_indicators"
                    continue

                dir_tf = ind_tf.get("signal_direction", "NEUTRAL")
                regime_tf = ind_tf.get("market_regime", "UNKNOWN")
                adx_tf = ind_tf.get("adx", 0)

                total += 1

                # Agreement: same direction or one is NEUTRAL (no conflict)
                if dir_tf == primary_direction:
                    agree_count += 1
                    details[tf] = f"agree_{dir_tf}"
                elif dir_tf == "NEUTRAL":
                    # Neutral doesn't disagree — counts as weak agreement
                    agree_count += 0.5
                    details[tf] = f"neutral"
                else:
                    details[tf] = f"conflict_{dir_tf}_vs_{primary_direction}"

                self.logger.debug(
                    f"   MTF {symbol} {tf}: dir={dir_tf}, regime={regime_tf}, ADX={adx_tf:.1f}"
                )

            except Exception as e:
                details[tf] = f"error:{str(e)[:30]}"
                self.logger.debug(f"   MTF {symbol} {tf}: ошибка {e}")

        # Require at least mtf_required agreements
        agreement = agree_count >= self.mtf_required and total > 0

        return {
            "agreement": agreement,
            "agree_count": agree_count,
            "total": total,
            "details": details,
        }
