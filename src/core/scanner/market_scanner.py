#!/usr/bin/env python3
import asyncio
from typing import List, Dict, Any
from src.core.market.trap_detector import detect_trap

class MarketScanner:
    def __init__(self, settings, logger, data_fetcher, risk_controller, strategy_engine):
        self.settings = settings; self.logger = logger; self.data_fetcher = data_fetcher
        self.risk_controller = risk_controller; self.strategy_engine = strategy_engine
        self.empty_scans_count = 0; self.successful_scans_count = 0
        self.current_min_adx = float(settings.get("min_adx", 10))
        self.current_min_atr = float(settings.get("min_atr_percent", 0.5))
        self.current_min_volume = float(settings.get("min_volume_24h_usdt", 50000))
        self.current_min_signal = float(settings.get("min_signal_strength", 0.25))
        self.use_spread_filter = settings.get("use_spread_filter", True)
        self.max_spread_pct = float(settings.get("max_spread_percent", 0.5))
        self.max_funding_rate = float(settings.get("max_funding_rate", 0.0))
        self.use_multi_timeframe = settings.get("use_multi_timeframe", True)
        self.mtf_timeframes = settings.get("mtf_timeframes", ["1h", "4h"])
        self.mtf_required = int(settings.get("mtf_required_agreement", 2))
        self.trap_detector = settings.get("trap_detector_enabled", True)
        self.aggressive = settings.get("aggressive_adaptation", True)
        self.fast_mode = settings.get("fast_mode_empty_scans", True)
        self.whitelist = settings.get("symbols_whitelist", [])
        self.blacklist = settings.get("blacklist", [])
        self._last_scan_time = 0; self._scan_stats = {"total": 0, "passed": 0, "by_filter": {}}

    def adapt_for_balance(self, balance):
        if balance < 100: self.mtf_required = 1
        elif balance < 1000: self.mtf_required = min(2, len(self.mtf_timeframes))
        else: self.mtf_required = int(self.settings.get("mtf_required_agreement", 2))

    def _adapt_filters(self):
        threshold = 1 if self.aggressive else 2
        if self.empty_scans_count >= threshold:
            old = {"adx": self.current_min_adx, "atr": self.current_min_atr, "vol": self.current_min_volume, "sig": self.current_min_signal}
            decay = 0.75 if self.aggressive else 0.85
            self.current_min_adx = max(4.0, self.current_min_adx * decay)
            self.current_min_atr = max(0.15, self.current_min_atr * decay)
            self.current_min_volume = max(5000, self.current_min_volume * decay)
            self.current_min_signal = max(0.12, self.current_min_signal * decay)
            self.logger.info(f"🔄 Адаптация: ADX {old['adx']:.1f}→{self.current_min_adx:.1f}, ATR {old['atr']:.2f}%→{self.current_min_atr:.2f}%, Vol {old['vol']:,.0f}→{self.current_min_volume:,.0f}, Sig {old['sig']:.2f}→{self.current_min_signal:.2f}")
            self.empty_scans_count = 0
        elif self.successful_scans_count >= 3:
            base_adx = float(self.settings.get("min_adx", 10)); base_atr = float(self.settings.get("min_atr_percent", 0.5))
            base_vol = float(self.settings.get("min_volume_24h_usdt", 50000)); base_sig = float(self.settings.get("min_signal_strength", 0.25))
            restore = 1.08
            self.current_min_adx = min(base_adx, self.current_min_adx * restore)
            self.current_min_atr = min(base_atr, self.current_min_atr * restore)
            self.current_min_volume = min(base_vol, self.current_min_volume * restore)
            self.current_min_signal = min(base_sig, self.current_min_signal * restore)
            self.successful_scans_count = 0

    async def scan_async(self, balance, max_pairs=100, max_asset_price_ratio=0.5, ignore_session_check=False):
        self.adapt_for_balance(balance); self._adapt_filters()
        self.logger.info(f"🔎 Сканирование (баланс: ${balance:.2f}, ADX≥{self.current_min_adx:.1f}, ATR≥{self.current_min_atr:.2f}%, Vol≥{self.current_min_volume:,.0f}, Sig≥{self.current_min_signal:.2f})")
        contracts = await self.data_fetcher.get_all_usdt_contracts()
        if not contracts: self.logger.error("❌ Не удалось получить список пар"); return []
        self.logger.info(f"📋 Получено {len(contracts)} контрактов")
        filtered_count = {"total":0,"whitelist":0,"blacklist":0,"ticker_fail":0,"volume":0,"funding":0,"spread":0,"klines_fail":0,"indicators_fail":0,"neutral":0,"adx":0,"atr":0,"signal":0,"mtf_reject":0,"trap":0,"passed":0}
        candidates = []; symbols_to_scan = []
        for c in contracts[:max_pairs]:
            symbol = c.get("symbol", "").replace("-", "/")
            if not symbol: continue
            filtered_count["total"] += 1
            if self.whitelist:
                clean = symbol.replace("/", "-")
                if clean not in self.whitelist and symbol not in self.whitelist: filtered_count["whitelist"] += 1; continue
            if self.blacklist:
                clean = symbol.replace("/", "-")
                if clean in self.blacklist or symbol in self.blacklist: filtered_count["blacklist"] += 1; continue
            symbols_to_scan.append(symbol)
        batch_size = 20 if self.fast_mode else 15
        for i in range(0, len(symbols_to_scan), batch_size):
            batch = symbols_to_scan[i:i+batch_size]
            tasks = [self._analyze_symbol(s, filtered_count) for s in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for res in results:
                if isinstance(res, dict) and res: candidates.append(res)
            await asyncio.sleep(0.02 if self.fast_mode else 0.05)
        self.logger.info(f"📊 Фильтрация: всего={filtered_count['total']}, wl={filtered_count['whitelist']}, bl={filtered_count['blacklist']}, ticker={filtered_count['ticker_fail']}, vol={filtered_count['volume']}, fund={filtered_count['funding']}, spread={filtered_count['spread']}, klines={filtered_count['klines_fail']}, ind={filtered_count['indicators_fail']}, neutral={filtered_count['neutral']}, adx={filtered_count['adx']}, atr={filtered_count['atr']}, signal={filtered_count['signal']}, mtf={filtered_count['mtf_reject']}, trap={filtered_count['trap']}, passed={filtered_count['passed']}")
        if not candidates:
            self.empty_scans_count += 1; self.successful_scans_count = 0
            self.logger.info(f"📭 Сигналов не найдено (пустых подряд: {self.empty_scans_count})")
        else:
            self.empty_scans_count = 0; self.successful_scans_count += 1
            candidates.sort(key=lambda x: x["indicators"].get("signal_strength", 0) * x["indicators"].get("adx", 0) * x["indicators"].get("atr_percent", 0), reverse=True)
            top = candidates[:5]
            if top:
                self.logger.info(f"✅ Найдено {len(candidates)} сигналов, топ-{len(top)}")
                for i, c in enumerate(top[:3], 1):
                    ind = c["indicators"]
                    self.logger.info(f" #{i} {c['symbol']}: {ind.get('signal_direction')} [{ind.get('market_regime')}] | ADX={ind.get('adx',0):.1f} | ATR={ind.get('atr_percent',0):.2f}% | Sig={ind.get('signal_strength',0):.2f} | RSI={ind.get('rsi',0):.1f} | Type={ind.get('entry_type','unknown')}")
        self._scan_stats = {"total": filtered_count["total"], "passed": filtered_count["passed"], "by_filter": filtered_count}
        return top if candidates else []

    async def _analyze_symbol(self, symbol, filtered_count):
        tf = self.settings.get("timeframe", "15m")
        ticker = await self.data_fetcher.get_ticker_data(symbol)
        if not ticker: filtered_count["ticker_fail"] += 1; return {}
        volume_24h = ticker.get("volume24h", 0); funding_rate = ticker.get("fundingRate", 0)
        last_price = ticker.get("lastPrice", 0); bid = ticker.get("bid", 0); ask = ticker.get("ask", 0)
        if volume_24h <= 0:
            try:
                df_vol = await self.data_fetcher.fetch_klines_async(None, symbol, interval="1d", limit=2)
                if df_vol is not None and not df_vol.empty and len(df_vol) >= 1:
                    volume_24h = float(df_vol["volume"].iloc[-1]) * float(df_vol["close"].iloc[-1])
            except Exception: pass
        if volume_24h < self.current_min_volume: filtered_count["volume"] += 1; return {}
        if abs(funding_rate) > abs(self.max_funding_rate) and self.max_funding_rate != 0: filtered_count["funding"] += 1; return {}
        if self.use_spread_filter and last_price > 0 and bid > 0 and ask > 0:
            spread_pct = (ask - bid) / last_price * 100
            if spread_pct > self.max_spread_pct: filtered_count["spread"] += 1; return {}
        df = await self.data_fetcher.fetch_klines_async(None, symbol, interval=tf, limit=80)
        if df is None or df.empty: filtered_count["klines_fail"] += 1; return {}
        indicators = self.data_fetcher.compute_indicators(df)
        if not indicators: filtered_count["indicators_fail"] += 1; return {}
        adx = indicators.get("adx", 0); atr_pct = indicators.get("atr_percent", 0)
        direction = indicators.get("signal_direction", "NEUTRAL")
        signal_strength = indicators.get("signal_strength", 0)
        rsi = indicators.get("rsi", 0); regime = indicators.get("market_regime", "UNKNOWN")
        entry_type = indicators.get("entry_type", "none")
        if direction == "NEUTRAL": filtered_count["neutral"] += 1; return {}
        if adx < self.current_min_adx: filtered_count["adx"] += 1; return {}
        if atr_pct < self.current_min_atr: filtered_count["atr"] += 1; return {}
        if signal_strength < self.current_min_signal: filtered_count["signal"] += 1; return {}
        if self.trap_detector:
            trap = detect_trap(indicators)
            if trap["is_trap"] and trap["confidence"] > 0.5:
                filtered_count["trap"] += 1; self.logger.debug(f"🪤 {symbol}: ловушка ({trap['reason']})"); return {}
        if self.use_multi_timeframe:
            mtf_result = await self._check_multi_timeframe(symbol, direction)
            if not mtf_result["agreement"]: filtered_count["mtf_reject"] += 1; return {}
            indicators["mtf_agreement"] = mtf_result["agree_count"]; indicators["mtf_total"] = mtf_result["total"]
        indicators["volume_24h"] = volume_24h; indicators["funding_rate"] = funding_rate
        indicators["close_price"] = last_price; indicators["spread_pct"] = ((ask - bid) / last_price * 100) if last_price > 0 else 0
        filtered_count["passed"] += 1
        self.logger.info(f"✅ {symbol}: СИГНАЛ {direction} [{regime}] | ADX={adx:.1f} | ATR={atr_pct:.2f}% | Sig={signal_strength:.2f} | RSI={rsi:.1f} | Vol={volume_24h:,.0f} | Type={entry_type}")
        return {"symbol": symbol, "indicators": indicators, "ticker": ticker}

    async def _check_multi_timeframe(self, symbol, primary_direction):
        agree_count = 0.0; total = 0
        for tf in self.mtf_timeframes:
            try:
                df_tf = await self.data_fetcher.fetch_klines_async(None, symbol, interval=tf, limit=50)
                if df_tf is None or df_tf.empty: continue
                ind_tf = self.data_fetcher.compute_indicators(df_tf)
                if not ind_tf: continue
                dir_tf = ind_tf.get("signal_direction", "NEUTRAL"); total += 1
                if dir_tf == primary_direction: agree_count += 1
                elif dir_tf == "NEUTRAL": agree_count += 0.5
            except Exception: pass
        return {"agreement": agree_count >= self.mtf_required and total > 0, "agree_count": agree_count, "total": total}

    def get_scan_stats(self): return dict(self._scan_stats)
