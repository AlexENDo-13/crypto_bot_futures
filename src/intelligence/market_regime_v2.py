#!/usr/bin/env python3
"""
Market Regime Detector v2 (B4) — adapts to market conditions.
Detects: TRENDING_UP, TRENDING_DOWN, RANGING, VOLATILE, CHOPPY
"""
import json
import os
import time
import logging
from collections import deque
from typing import Dict, Any, List, Optional, Tuple
import statistics

logger = logging.getLogger("CryptoBot.Regime")

class MarketRegimeV2:
    def __init__(self, history_path: str = "logs/market_regime.json", lookback: int = 50):
        self.history_path = history_path
        self.lookback = lookback
        self._price_history: deque = deque(maxlen=lookback)
        self._atr_history: deque = deque(maxlen=lookback)
        self._volume_history: deque = deque(maxlen=lookback)
        self._regime_history: deque = deque(maxlen=20)
        self._current_regime = "UNKNOWN"
        self._regime_confidence = 0.0
        self._regime_since = time.time()
        self._regime_stats: Dict[str, Dict] = {}
        self._load()

    def _load(self):
        if os.path.exists(self.history_path):
            try:
                with open(self.history_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._regime_stats = data.get("regime_stats", {})
                logger.info(f"Regime stats loaded: {len(self._regime_stats)} regimes tracked")
            except Exception as e:
                logger.error(f"Regime load error: {e}")

    def _save(self):
        try:
            os.makedirs(os.path.dirname(self.history_path), exist_ok=True)
            with open(self.history_path, "w", encoding="utf-8") as f:
                json.dump({
                    "regime_stats": self._regime_stats,
                    "last_update": time.time()
                }, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Regime save error: {e}")

    def feed_data(self, prices: List[float], volumes: List[float] = None, atrs: List[float] = None):
        """Feed recent price/volume/ATR data for regime detection."""
        if prices:
            for p in prices:
                self._price_history.append(float(p))
        if volumes:
            for v in volumes:
                self._volume_history.append(float(v))
        if atrs:
            for a in atrs:
                self._atr_history.append(float(a))

    def detect_regime(self) -> str:
        """Detect current market regime based on recent data."""
        if len(self._price_history) < 20:
            return "UNKNOWN"

        prices = list(self._price_history)

        # 1. Trend strength (using linear regression slope)
        n = len(prices)
        x_mean = (n - 1) / 2
        y_mean = sum(prices) / n
        numerator = sum((i - x_mean) * (prices[i] - y_mean) for i in range(n))
        denominator = sum((i - x_mean) ** 2 for i in range(n))
        slope = numerator / denominator if denominator != 0 else 0
        slope_pct = (slope / prices[-1]) * 100 if prices[-1] > 0 else 0

        # 2. Volatility (std dev of returns)
        returns = [(prices[i] - prices[i-1]) / prices[i-1] * 100 for i in range(1, n) if prices[i-1] > 0]
        if len(returns) < 2:
            return "UNKNOWN"
        volatility = statistics.stdev(returns) if len(returns) > 1 else 0
        avg_return = sum(abs(r) for r in returns) / len(returns)

        # 3. ADX-like directional movement
        up_moves = sum(1 for i in range(1, n) if prices[i] > prices[i-1])
        down_moves = sum(1 for i in range(1, n) if prices[i] < prices[i-1])
        total_moves = up_moves + down_moves
        directional_index = abs(up_moves - down_moves) / total_moves if total_moves > 0 else 0

        # 4. Range-bound detection (price within channel)
        price_range = (max(prices) - min(prices)) / prices[-1] * 100 if prices[-1] > 0 else 0
        avg_candle = avg_return * 2

        # Classification
        regime = "UNKNOWN"
        confidence = 0.0

        if volatility > 3.0 and directional_index < 0.3:
            regime = "VOLATILE"
            confidence = min(100, volatility * 20)
        elif directional_index > 0.6 and abs(slope_pct) > 0.05:
            if slope_pct > 0:
                regime = "TRENDING_UP"
            else:
                regime = "TRENDING_DOWN"
            confidence = directional_index * 100
        elif price_range < volatility * 3 and directional_index < 0.4:
            regime = "RANGING"
            confidence = (1 - directional_index) * 100
        elif volatility < 0.5 and directional_index < 0.3:
            regime = "CHOPPY"
            confidence = 60
        else:
            regime = "MIXED"
            confidence = 40

        # Smooth regime changes
        if self._current_regime != regime:
            if time.time() - self._regime_since > 300:  # Minimum 5 min in regime
                old_regime = self._current_regime
                self._current_regime = regime
                self._regime_confidence = confidence
                self._regime_since = time.time()
                self._regime_history.append(regime)
                logger.info(f"REGIME CHANGE: {old_regime} -> {regime} (confidence={confidence:.0f}%)")
            else:
                regime = self._current_regime  # Stay in current regime

        return regime

    def get_recommended_settings(self) -> Dict[str, Any]:
        """Return recommended trading settings for current regime."""
        regime = self._current_regime
        base = {
            "TRENDING_UP": {
                "direction": "LONG_ONLY",
                "sl_multiplier": 1.0,
                "tp_multiplier": 1.5,
                "position_size_multiplier": 1.2,
                "leverage_cap": 1.0,
                "description": "Follow the trend, wider TP"
            },
            "TRENDING_DOWN": {
                "direction": "SHORT_ONLY",
                "sl_multiplier": 1.0,
                "tp_multiplier": 1.5,
                "position_size_multiplier": 1.2,
                "leverage_cap": 1.0,
                "description": "Follow the trend, wider TP"
            },
            "RANGING": {
                "direction": "BOTH",
                "sl_multiplier": 0.8,
                "tp_multiplier": 0.7,
                "position_size_multiplier": 0.8,
                "leverage_cap": 0.7,
                "description": "Tight SL/TP, smaller size"
            },
            "VOLATILE": {
                "direction": "BOTH",
                "sl_multiplier": 1.5,
                "tp_multiplier": 2.0,
                "position_size_multiplier": 0.5,
                "leverage_cap": 0.5,
                "description": "Wider stops, smaller size"
            },
            "CHOPPY": {
                "direction": "NONE",
                "sl_multiplier": 1.0,
                "tp_multiplier": 1.0,
                "position_size_multiplier": 0.3,
                "leverage_cap": 0.3,
                "description": "Avoid trading or minimal size"
            },
            "MIXED": {
                "direction": "BOTH",
                "sl_multiplier": 1.0,
                "tp_multiplier": 1.0,
                "position_size_multiplier": 0.8,
                "leverage_cap": 0.8,
                "description": "Cautious mode"
            },
            "UNKNOWN": {
                "direction": "BOTH",
                "sl_multiplier": 1.0,
                "tp_multiplier": 1.0,
                "position_size_multiplier": 1.0,
                "leverage_cap": 1.0,
                "description": "Default settings"
            }
        }
        return base.get(regime, base["UNKNOWN"])

    def should_trade(self, signal_direction: str = "BOTH") -> Tuple[bool, str]:
        """Check if trading is recommended in current regime."""
        rec = self.get_recommended_settings()
        direction = rec["direction"]

        if direction == "NONE":
            return False, f"Regime={self._current_regime}: avoid trading (choppy)"
        if direction == "LONG_ONLY" and signal_direction == "SHORT":
            return False, f"Regime={self._current_regime}: LONG only, blocking SHORT"
        if direction == "SHORT_ONLY" and signal_direction == "LONG":
            return False, f"Regime={self._current_regime}: SHORT only, blocking LONG"

        return True, f"Regime={self._current_regime}: OK for {signal_direction}"

    def record_trade(self, regime: str, pnl: float):
        """Record trade outcome for regime statistics."""
        if regime not in self._regime_stats:
            self._regime_stats[regime] = {"trades": 0, "wins": 0, "total_pnl": 0.0}
        self._regime_stats[regime]["trades"] += 1
        if pnl > 0:
            self._regime_stats[regime]["wins"] += 1
        self._regime_stats[regime]["total_pnl"] += pnl
        if self._regime_stats[regime]["trades"] % 5 == 0:
            self._save()

    def get_stats(self) -> Dict[str, Any]:
        return {
            "current_regime": self._current_regime,
            "confidence": self._regime_confidence,
            "regime_since": self._regime_since,
            "recommendations": self.get_recommended_settings(),
            "regime_performance": {
                r: {
                    "trades": s["trades"],
                    "win_rate": (s["wins"] / s["trades"] * 100) if s["trades"] > 0 else 0,
                    "total_pnl": s["total_pnl"]
                }
                for r, s in self._regime_stats.items()
            }
        }
