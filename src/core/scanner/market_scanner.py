#!/usr/bin/env python3
"""MarketScanner v11 — Fixed: scans MORE symbols, relaxed filters for micro balances, priority by volume."""
import asyncio
import time
import random
from typing import List, Dict, Any
from src.core.market.trap_detector import detect_trap

class MarketScanner:
    def __init__(self, settings, logger, data_fetcher, risk_controller, strategy_engine):
        self.settings = settings
        self.logger = logger
        self.data_fetcher = data_fetcher
        self.risk_controller = risk_controller
        self.strategy_engine = strategy_engine
        self.empty_scans_count = 0
        self.successful_scans_count = 0
        self.current_min_adx = float(settings.get("min_adx", 12))
        self.current_min_atr = float(settings.get("min_atr_percent", 0.3))
        self.current_min_volume = float(settings.get("min_volume_24h_usdt", 30000))
        self.current_min_signal = float(settings.get("min_signal_strength", 0.25))
        self.use_spread_filter = settings.get("use_spread_filter", True)
        self.max_spread_pct = float(settings.get("max_spread_percent", 0.8))
        self.max_funding_rate = float(settings.get("max_funding_rate", 0.0))

        self.primary_timeframe = settings.get("timeframe", "15m")
        self.mtf_timeframes = settings.get("mtf_timeframes", ["1h", "4h", "1d"])
        self.use_multi_timeframe = settings.get("use_multi_timeframe", True)
        self.mtf_required = int(settings.get("mtf_required_agreement", 2))

        self.trap_detector = settings.get("trap_detector_enabled", True)
        self.aggressive = settings.get("aggressive_adaptation", True)
        self.fast_mode = settings.get("fast_mode_empty_scans", True)
        self.whitelist = settings.get("symbols_whitelist", [])
        self.blacklist = settings.get("blacklist", ["SHIB-USDT","PEPE-USDT","FLOKI-USDT","BONK-USDT"])
        self._last_scan_time = 0
        self._scan_stats = {"total": 0, "passed": 0, "by_filter": {}}
        self._market_volatility = 0.5
        self._market_trend = "neutral"

        self._failed_symbols = {}
        self._max_symbol_fails = 3
        self._symbol_cooldown = {}
        self._cooldown_duration = 300
        self._scanned_symbols_history = []
        self._max_history = 50

        self._symbol_rotation_index = 0
        self._symbols_per_scan = 20

    def adapt_for_balance(self, balance):
        if balance < 50:
            self.mtf_required = 1
            self._symbols_per_scan = 30
            self.current_min_adx = max(8.0, self.current_min_adx * 0.8)
            self.current_min_atr = max(0.2, self.current_min_atr * 0.8)
            self.current_min_signal = max(0.2, self.current_min_signal * 0.8)
        elif balance < 200:
            self.mtf_required = min(2, len(self.mtf_timeframes))
            self._symbols_per_scan = 25
        else:
            self.mtf_required = int(self.settings.get("mtf_required_agreement", 2))
            self._symbols_per_scan = 20

    def _adapt_filters(self):
        threshold = 1 if self.aggressive else 2
        if self.empty_scans_count >= threshold:
            old = {"adx": self.current_min_adx, "atr": self.current_min_atr,
                   "vol": self.current_min_volume, "sig": self.current_min_signal}
            decay = 0.7 if self.aggressive else 0.85
            self.current_min_adx = max(5.0, self.current_min_adx * decay)
            self.current_min_atr = max(0.15, self.current_min_atr * decay)
            self.current_min_volume = max(5000, self.current_min_volume * decay)
            self.current_min_signal = max(0.15, self.current_min_signal * decay)
            self.logger.info(f"RELAXING filters (empty streak {self.empty_scans_count}): "
                             f"ADX {old['adx']:.1f}->{self.current_min_adx:.1f}, "
                             f"ATR {old['atr']:.2f}%->{self.current_min_atr:.2f}%, "
                             f"Vol {old['vol']:,.0f}->{self.current_min_volume:,.0f}, "
                             f"Sig {old['sig']:.2f}->{self.current_min_signal:.2f}")
            self.empty_scans_count = 0
        elif self.successful_scans_count >= 3:
            base_adx = float(self.settings.get("min_adx", 12))
            base_atr = float(self.settings.get("min_atr_percent", 0.3))
            base_vol = float(self.settings.get("min_volume_24h_usdt", 30000))
            base_sig = float(self.settings.get("min_signal_strength", 0.25))
            restore = 1.08
            self.current_min_adx = min(base_adx, self.current_min_adx * restore)
            self.current_min_atr = min(base_atr, self.current_min_atr * restore)
            self.current_min_volume = min(base_vol, self.current_min_volume * restore)
            self.current_min_signal = min(base_sig, self.current_min_signal * restore)
            self.successful_scans_count = 0

    def _is_symbol_available(self, symbol):
        now = time.time()
        if symbol in self._symbol_cooldown:
            if now < self._symbol_cooldown[symbol]:
                return False
            else:
                del self._symbol_cooldown[symbol]
        if symbol in self._failed_symbols:
            if self._failed_symbols[symbol] >= self._max_symbol_fails:
                return False
        return True

    def _mark_symbol_failed(self, symbol):
        self._failed_symbols[symbol] = self._failed_symbols.get(symbol, 0) + 1
        if self._failed_symbols[symbol] >= self._max_symbol_fails:
            self.logger.warning(f"Symbol {symbol} failed {self._max_symbol_fails} times, cooling down for 5min")
            self._symbol_cooldown[symbol] = time.time() + self._cooldown_duration

    def _mark_symbol_success(self, symbol):
        if symbol in self._failed_symbols:
            del self._failed_symbols[symbol]
        if symbol in self._symbol_cooldown:
            del self._symbol_cooldown[symbol]

    async def scan_async(self, balance, max_pairs=100, max_asset_price_ratio=0.5, ignore_session_check=False):
        self.adapt_for_balance(balance)
        self._adapt_filters()
        self.logger.info(f"=== SCAN START === balance=${balance:.2f} | primary={self.primary_timeframe} | "
                         f"ADX>={self.current_min_adx:.1f} | ATR>={self.current_min_atr:.2f}% | "
                         f"Sig>={self.current_min_signal:.2f} | MTF_need={self.mtf_required}")

        contracts = await self.data_fetcher.get_all_usdt_contracts()
        if not contracts:
            self.logger.warning("Contracts API failed, using whitelist if configured")
            if self.whitelist:
                contracts = [{"symbol": s} for s in self.whitelist]
            else:
                return []
        elif self.whitelist:
            whitelist_set = set(self.whitelist)
            contracts = [c for c in contracts if c.get("symbol", "") in whitelist_set]

        self.logger.info(f"Total symbols available: {len(contracts)}")
        filtered_count = {
            "total": 0, "blacklist": 0, "ticker_fail": 0, "volume": 0,
            "funding": 0, "spread": 0, "klines_fail": 0, "indicators_fail": 0,
            "neutral": 0, "adx": 0, "atr": 0, "signal": 0, "mtf_reject": 0,
            "trap": 0, "passed": 0, "cooldown": 0, "max_fails": 0
        }
        candidates = []
        symbols_to_scan = []

        for c in contracts:
            symbol = c.get("symbol", "").replace("-", "/")
            if not symbol:
                continue
            filtered_count["total"] += 1
            if self.blacklist:
                clean = symbol.replace("/", "-")
                if clean in self.blacklist or symbol in self.blacklist:
                    filtered_count["blacklist"] += 1
                    continue
            if not self._is_symbol_available(symbol):
                if symbol in self._symbol_cooldown:
                    filtered_count["cooldown"] += 1
                else:
                    filtered_count["max_fails"] += 1
                continue
            symbols_to_scan.append((symbol, c))

        if not symbols_to_scan:
            self.logger.warning("No symbols available to scan")
            self.empty_scans_count += 1
            return []

        # Priority: sort by estimated volume (if available), then shuffle remainder
        symbols_to_scan.sort(key=lambda x: float(x[1].get("volume24h", x[1].get("quoteVolume", 0)) or 0), reverse=True)
        top_vol = symbols_to_scan[:self._symbols_per_scan]
        rest = symbols_to_scan[self._symbols_per_scan:]
        random.shuffle(rest)
        scan_subset = top_vol + rest[:max(0, self._symbols_per_scan - len(top_vol))]
        scan_subset = [s[0] for s in scan_subset]
        self.logger.info(f"Scanning {len(scan_subset)} symbols (top by volume + random)")

        batch_size = min(5, len(scan_subset))
        for i in range(0, len(scan_subset), batch_size):
            batch = scan_subset[i:i+batch_size]
            tasks = [self._analyze_symbol(s, filtered_count) for s in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for sym, res in zip(batch, results):
                if isinstance(res, Exception):
                    self.logger.debug(f"Symbol {sym} analysis exception: {res}")
                    self._mark_symbol_failed(sym)
                elif isinstance(res, dict) and res:
                    candidates.append(res)
                    self._mark_symbol_success(sym)
                else:
                    self._mark_symbol_failed(sym)
            if i + batch_size < len(scan_subset):
                await asyncio.sleep(1.0)

        self.logger.info(f"Filter stats: total={filtered_count['total']}, passed={filtered_count['passed']}, "
                         f"ticker_fail={filtered_count['ticker_fail']}, vol={filtered_count['volume']}, "
                         f"klines={filtered_count['klines_fail']}, adx={filtered_count['adx']}, "
                         f"atr={filtered_count['atr']}, signal={filtered_count['signal']}, "
                         f"mtf={filtered_count['mtf_reject']}, trap={filtered_count['trap']}, "
                         f"neutral={filtered_count['neutral']}")

        if not candidates:
            self.empty_scans_count += 1
            self.successful_scans_count = 0
            self.logger.info(f"No signals found (empty streak: {self.empty_scans_count})")
        else:
            self.empty_scans_count = 0
            self.successful_scans_count += 1
            candidates.sort(key=lambda x: x["indicators"].get("signal_strength", 0) *
                                         x["indicators"].get("adx", 0) *
                                         x["indicators"].get("atr_percent", 0), reverse=True)
            top = candidates[:5]
            self.logger.info(f"FOUND {len(candidates)} signals, top-{len(top)}:")
            for i, c in enumerate(top[:3], 1):
                ind = c["indicators"]
                details = ", ".join(ind.get("signal_details", [])[:3])
                self.logger.info(f"  #{i} {c['symbol']}: {ind.get('signal_direction')} [{ind.get('market_regime')}] | "
                                 f"ADX={ind.get('adx',0):.1f} | ATR={ind.get('atr_percent',0):.2f}% | "
                                 f"Sig={ind.get('signal_strength',0):.2f} | RSI={ind.get('rsi',0):.1f} | "
                                 f"MTF={ind.get('mtf_agreement',0)}/{ind.get('mtf_total',0)} | {details}")
        self._scan_stats = {"total": filtered_count["total"], "passed": filtered_count["passed"], "by_filter": filtered_count}
        return top if candidates else []

    async def _analyze_symbol(self, symbol, filtered_count):
        # Step 1: Ticker
        try:
            ticker = await self.data_fetcher.get_ticker_data(symbol)
        except Exception as e:
            self.logger.debug(f"Ticker error {symbol}: {e}")
            ticker = None
        if not ticker:
            filtered_count["ticker_fail"] += 1
            return {}

        volume_24h = ticker.get("volume24h", 0)
        funding_rate = ticker.get("fundingRate", 0)
        last_price = ticker.get("lastPrice", 0)
        bid = ticker.get("bid", 0)
        ask = ticker.get("ask", 0)

        if volume_24h < self.current_min_volume:
            filtered_count["volume"] += 1
            return {}
        if abs(funding_rate) > abs(self.max_funding_rate) and self.max_funding_rate != 0:
            filtered_count["funding"] += 1
            return {}
        if self.use_spread_filter and last_price > 0 and bid > 0 and ask > 0:
            spread_pct = (ask - bid) / last_price * 100
            if spread_pct > self.max_spread_pct:
                filtered_count["spread"] += 1
                return {}

        # Step 2: Primary timeframe
        try:
            df_primary = await self.data_fetcher.fetch_klines_async(None, symbol, interval=self.primary_timeframe, limit=80)
        except Exception as e:
            self.logger.debug(f"Primary klines error {symbol}: {e}")
            df_primary = None
        if df_primary is None or df_primary.empty:
            filtered_count["klines_fail"] += 1
            return {}

        indicators = self.data_fetcher.compute_indicators(df_primary)
        if not indicators:
            filtered_count["indicators_fail"] += 1
            return {}

        adx = indicators.get("adx", 0)
        atr_pct = indicators.get("atr_percent", 0)
        direction = indicators.get("signal_direction", "NEUTRAL")
        signal_strength = indicators.get("signal_strength", 0)
        rsi = indicators.get("rsi", 0)
        regime = indicators.get("market_regime", "UNKNOWN")
        entry_type = indicators.get("entry_type", "mixed")
        signal_details = indicators.get("signal_details", [])

        if direction == "NEUTRAL":
            filtered_count["neutral"] += 1
            return {}
        if adx < self.current_min_adx:
            filtered_count["adx"] += 1
            return {}
        if atr_pct < self.current_min_atr:
            filtered_count["atr"] += 1
            return {}
        if signal_strength < self.current_min_signal:
            filtered_count["signal"] += 1
            return {}

        # Step 3: Multi-timeframe
        mtf_score = 0
        mtf_total = 0
        mtf_details = []
        if self.use_multi_timeframe and self.mtf_timeframes:
            for tf in self.mtf_timeframes:
                try:
                    df_tf = await self.data_fetcher.fetch_klines_async(None, symbol, interval=tf, limit=50)
                    if df_tf is None or df_tf.empty:
                        continue
                    ind_tf = self.data_fetcher.compute_indicators(df_tf)
                    if not ind_tf:
                        continue
                    dir_tf = ind_tf.get("signal_direction", "NEUTRAL")
                    tf_adx = ind_tf.get("adx", 0)
                    mtf_total += 1
                    if dir_tf == direction:
                        mtf_score += 1
                        mtf_details.append(f"{tf}:{dir_tf}(ADX={tf_adx:.1f})")
                    elif dir_tf == "NEUTRAL":
                        mtf_score += 0.3
                        mtf_details.append(f"{tf}:neutral")
                    else:
                        mtf_details.append(f"{tf}:{dir_tf}(opp)")
                except Exception as e:
                    self.logger.debug(f"MTF error {symbol} {tf}: {e}")
                    continue

        # RELAXED MTF: if no MTF data available, allow signal
        effective_mtf_required = self.mtf_required if mtf_total > 0 else 0
        if mtf_total > 0 and mtf_score < effective_mtf_required:
            filtered_count["mtf_reject"] += 1
            self.logger.debug(f"MTF reject {symbol}: {mtf_score:.1f}/{effective_mtf_required} required")
            return {}

        # Step 4: Trap detection
        if self.trap_detector:
            try:
                trap = detect_trap(indicators)
                if trap.get("is_trap") and trap.get("confidence", 0) > 0.6:
                    filtered_count["trap"] += 1
                    return {}
            except Exception:
                pass

        indicators["volume_24h"] = volume_24h
        indicators["funding_rate"] = funding_rate
        indicators["close_price"] = last_price
        indicators["spread_pct"] = ((ask - bid) / last_price * 100) if last_price > 0 else 0
        indicators["mtf_agreement"] = mtf_score
        indicators["mtf_total"] = mtf_total
        indicators["mtf_details"] = mtf_details

        explanation = (f"SIGNAL {symbol}: {direction} [{regime}] | EntryType={entry_type} | "
                       f"ADX={adx:.1f} | ATR={atr_pct:.2f}% | Sig={signal_strength:.2f} | RSI={rsi:.1f} | "
                       f"Vol=${volume_24h:,.0f} | MTF={mtf_score:.1f}/{mtf_total} | "
                       f"Details: {', '.join(signal_details[:4])}")
        self.logger.info(explanation)
        filtered_count["passed"] += 1
        return {"symbol": symbol, "indicators": indicators, "ticker": ticker}

    def get_scan_stats(self):
        return {
            **self._scan_stats,
            "market_trend": self._market_trend,
            "market_volatility": self._market_volatility,
            "empty_streak": self.empty_scans_count,
            "failed_symbols_count": len(self._failed_symbols),
            "cooldown_symbols_count": len(self._symbol_cooldown),
        }
