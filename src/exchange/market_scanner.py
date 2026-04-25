"""
CryptoBot v9.0 - Neural Market Scanner
Features: Async scanning, neural composite scoring, regime detection,
          volatility-adjusted thresholds, sentiment analysis hook
"""
import logging
import time
import asyncio
from typing import Dict, List, Optional, Any, Set
import pandas as pd
import numpy as np

from exchange.data_fetcher import DataFetcher
from strategies.strategies import StrategyManager, Signal
from ml.ml_engine import MLEngine

class MarketScanner:
    """Neural adaptive market scanner."""

    def __init__(self, data_fetcher: DataFetcher = None,
                 strategy_manager: StrategyManager = None,
                 ml_engine: MLEngine = None,
                 max_workers: int = 4):
        self.data_fetcher = data_fetcher or DataFetcher()
        self.strategies = strategy_manager or StrategyManager()
        self.ml = ml_engine or MLEngine()
        self.logger = logging.getLogger("CryptoBot.Scanner")
        self.max_workers = max_workers

        self.symbols: List[str] = []
        self.scan_results: List[Dict] = []
        self.last_scan_time: float = 0
        self._scan_lock = asyncio.Lock()
        self._min_scan_interval = 5
        self._last_signals: Dict[str, float] = {}
        self._signal_cooldown = 60
        self._market_regime = "neutral"
        self._volatility_cache: Dict[str, float] = {}
        self._sentiment_scores: Dict[str, float] = {}

        self.logger.info("MarketScanner v9.0 | strategies=%d", len(self.strategies.strategies))

    async def load_symbols(self, count: int = 15) -> List[str]:
        self.symbols = await self.data_fetcher.load_symbols(count)
        self.logger.info("Loaded %d symbols for scanning", len(self.symbols))
        return self.symbols

    def _detect_market_regime(self, df: pd.DataFrame) -> str:
        try:
            if len(df) < 50:
                return "neutral"
            returns = df["close"].pct_change().dropna()
            volatility = returns.std() * np.sqrt(len(returns))
            adx = self._calculate_adx(df)
            if volatility > 0.03:
                return "volatile"
            elif adx > 25:
                return "trending"
            else:
                return "ranging"
        except Exception:
            return "neutral"

    def _calculate_adx(self, df: pd.DataFrame, period: int = 14) -> float:
        try:
            high, low, close = df["high"], df["low"], df["close"]
            plus_dm = high.diff().clip(lower=0)
            minus_dm = (-low.diff()).clip(lower=0)
            tr1 = high - low
            tr2 = abs(high - close.shift(1))
            tr3 = abs(low - close.shift(1))
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            atr = tr.rolling(window=period).mean()
            plus_di = 100 * plus_dm.rolling(window=period).mean() / atr
            minus_di = 100 * minus_dm.rolling(window=period).mean() / atr
            dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
            adx = dx.rolling(window=period).mean()
            return float(adx.iloc[-1]) if not pd.isna(adx.iloc[-1]) else 0.0
        except Exception:
            return 0.0

    def _calculate_neural_score(self, signal: Signal, df: pd.DataFrame) -> float:
        base_conf = signal.confidence

        try:
            returns = df["close"].pct_change().dropna()
            vol = returns.std()
            vol_score = 1.0 if 0.005 < vol < 0.03 else 0.7 if vol < 0.05 else 0.5
        except Exception:
            vol_score = 1.0

        try:
            vol_sma = df["volume"].rolling(20).mean().iloc[-1]
            curr_vol = df["volume"].iloc[-1]
            vol_ratio = curr_vol / vol_sma if vol_sma > 0 else 1.0
            volume_score = min(vol_ratio / 2.0, 1.0)
        except Exception:
            volume_score = 0.5

        try:
            sma20 = df["close"].rolling(20).mean().iloc[-1]
            sma50 = df["close"].rolling(50).mean().iloc[-1]
            price = df["close"].iloc[-1]
            if signal.type.value == "buy":
                trend_score = 1.0 if price > sma20 > sma50 else 0.7 if price > sma20 else 0.4
            else:
                trend_score = 1.0 if price < sma20 < sma50 else 0.7 if price < sma20 else 0.4
        except Exception:
            trend_score = 0.5

        try:
            delta = df["close"].diff()
            gain = delta.clip(lower=0).rolling(14).mean()
            loss = (-delta.clip(upper=0)).rolling(14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            rsi_val = float(rsi.iloc[-1])
            if signal.type.value == "buy":
                momentum_score = 1.0 if 40 < rsi_val < 70 else 0.7 if rsi_val < 40 else 0.5
            else:
                momentum_score = 1.0 if 30 < rsi_val < 60 else 0.7 if rsi_val > 60 else 0.5
        except Exception:
            momentum_score = 0.5

        sentiment_score = self._sentiment_scores.get(signal.symbol, 0.5)

        composite = (
            base_conf * 0.35 +
            vol_score * 0.15 +
            volume_score * 0.10 +
            trend_score * 0.15 +
            momentum_score * 0.15 +
            sentiment_score * 0.10
        )
        return min(composite, 1.0)

    def _update_sentiment(self, symbol: str, score: float):
        self._sentiment_scores[symbol] = max(0.0, min(1.0, score))

    async def scan_symbol(self, symbol: str, timeframe: str = "15m",
                          min_confidence: float = 0.4,
                          enabled_strategies: List[str] = None) -> List[Signal]:
        try:
            now = time.time()
            last_time = self._last_signals.get(symbol, 0)
            if now - last_time < self._signal_cooldown:
                return []

            df = await self.data_fetcher.get_klines(symbol, timeframe)
            if df is None or len(df) < 50:
                self.logger.debug("%s: insufficient data (%s)", symbol, len(df) if df is not None else "None")
                return []

            self.logger.debug("%s: loaded %d candles", symbol, len(df))

            regime = self._detect_market_regime(df)
            self._market_regime = regime

            # Adaptive threshold - more lenient
            adjusted_min = min_confidence
            if regime == "volatile":
                adjusted_min = min_confidence * 1.1  # Was 1.2, now more lenient
            elif regime == "ranging":
                adjusted_min = min_confidence * 0.85  # Was 0.9, now more lenient

            raw_signals = self.strategies.analyze_all(df, symbol, adjusted_min, enabled_strategies)
            self.logger.debug("%s: raw signals=%d regime=%s min_conf=%.2f", symbol, len(raw_signals), regime, adjusted_min)

            # Neural scoring
            for sig in raw_signals:
                sig.confidence = self._calculate_neural_score(sig, df)
                sig.metadata = sig.metadata or {}
                sig.metadata["regime"] = regime
                sig.metadata["neural_score"] = sig.confidence

            # ML filtering
            if self.ml.trained:
                filtered = []
                for signal in raw_signals:
                    try:
                        features = self.ml.extract_features(df)
                        passed, score = self.ml.filter_signal(signal.confidence, features)
                        if passed:
                            signal.confidence = score
                            filtered.append(signal)
                    except Exception as e:
                        self.logger.debug("ML filter error: %s", e)
                        filtered.append(signal)
                raw_signals = filtered
                self.logger.debug("%s: after ML filter=%d", symbol, len(raw_signals))

            # Final confidence filter
            signals = [s for s in raw_signals if s.confidence >= min_confidence]
            self.logger.debug("%s: final signals=%d (after conf filter >= %.2f)", symbol, len(signals), min_confidence)

            if signals:
                self._last_signals[symbol] = now
                for s in signals:
                    self.logger.info("%s: SIGNAL %s %s conf=%.3f neural=%.3f", 
                                     symbol, s.type.value.upper(), s.strategy, s.confidence,
                                     s.metadata.get("neural_score", 0) if s.metadata else 0)

            return signals

        except Exception as e:
            self.logger.error("Scan error for %s: %s", symbol, e)
            return []

    async def scan_all(self, timeframe: str = "15m", min_confidence: float = 0.4,
                       enabled_strategies: List[str] = None) -> List[Signal]:
        async with self._scan_lock:
            now = time.time()
            if now - self.last_scan_time < self._min_scan_interval:
                self.logger.debug("Scan skipped: too soon")
                return []

            if not self.symbols:
                await self.load_symbols()

            self.logger.info("Scanning %d symbols on %s...", len(self.symbols), timeframe)
            all_signals: List[Signal] = []
            seen: Set[str] = set()

            # Pre-fetch prices
            try:
                await self.data_fetcher.get_prices_batch(self.symbols)
            except Exception:
                pass

            # Concurrent scanning with semaphore
            sem = asyncio.Semaphore(self.max_workers)

            async def scan_with_limit(sym):
                async with sem:
                    return await self.scan_symbol(sym, timeframe, min_confidence, enabled_strategies)

            tasks = [scan_with_limit(sym) for sym in self.symbols]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            total_raw = 0
            for sym, signals in zip(self.symbols, results):
                if isinstance(signals, Exception):
                    self.logger.error("Scan failed for %s: %s", sym, signals)
                    continue
                if signals:
                    total_raw += len(signals)
                    for sig in signals:
                        key = "%s_%s_%s" % (sig.symbol, sig.strategy, sig.type.value)
                        if key not in seen:
                            seen.add(key)
                            all_signals.append(sig)
                    self.logger.info("%s: %d signals", sym, len(signals))

            all_signals.sort(key=lambda s: s.confidence, reverse=True)

            self.scan_results = [
                {
                    "symbol": s.symbol, "strategy": s.strategy,
                    "type": s.type.value, "confidence": round(s.confidence, 3),
                    "price": round(s.price, 4), "time": s.timestamp,
                    "regime": s.metadata.get("regime", "unknown") if s.metadata else "unknown",
                    "neural_score": s.metadata.get("neural_score", 0) if s.metadata else 0
                }
                for s in all_signals
            ]

            self.last_scan_time = time.time()
            self.logger.info("Scan complete | %d unique signals (from %d raw) | regime=%s", 
                             len(all_signals), total_raw, self._market_regime)
            return all_signals

    def get_top_signals(self, n: int = 10) -> List[Dict]:
        return self.scan_results[:n]
