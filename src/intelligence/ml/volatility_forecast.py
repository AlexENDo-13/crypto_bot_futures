#!/usr/bin/env python3
"""
Volatility Forecast (C3) — predicts future ATR using EWMA + GARCH-like approach.
"""
import json
import os
import time
import logging
import math
from collections import deque
from typing import Dict, Any, List, Optional
import numpy as np

logger = logging.getLogger("CryptoBot.VolForecast")

class VolatilityForecaster:
    def __init__(self, data_path: str = "logs/volatility_forecast.json",
                 lookback: int = 50):
        self.data_path = data_path
        self.lookback = lookback
        self._returns_history: Dict[str, deque] = {}  # per symbol
        self._atr_history: Dict[str, deque] = {}      # per symbol
        self._forecasts: Dict[str, Dict] = {}          # per symbol
        self._last_update = 0
        self._update_interval = 300  # 5 min
        self._load()

    def _load(self):
        if os.path.exists(self.data_path):
            try:
                with open(self.data_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for sym, vals in data.get("returns", {}).items():
                        self._returns_history[sym] = deque(vals, maxlen=self.lookback)
                    for sym, vals in data.get("atr", {}).items():
                        self._atr_history[sym] = deque(vals, maxlen=self.lookback)
                logger.info(f"Vol forecast loaded: {len(self._returns_history)} symbols")
            except Exception as e:
                logger.error(f"Vol forecast load error: {e}")

    def _save(self):
        try:
            os.makedirs(os.path.dirname(self.data_path), exist_ok=True)
            with open(self.data_path, "w", encoding="utf-8") as f:
                json.dump({
                    "returns": {k: list(v) for k, v in self._returns_history.items()},
                    "atr": {k: list(v) for k, v in self._atr_history.items()},
                    "last_update": time.time()
                }, f, indent=2)
        except Exception as e:
            logger.error(f"Vol forecast save error: {e}")

    def feed_price(self, symbol: str, price: float, atr_percent: float = None):
        """Feed new price for a symbol."""
        if symbol not in self._returns_history:
            self._returns_history[symbol] = deque(maxlen=self.lookback)
            self._atr_history[symbol] = deque(maxlen=self.lookback)

        # Calculate return if we have previous price
        if len(self._returns_history[symbol]) > 0:
            prev_prices = list(self._returns_history[symbol])
            # Store prices, calculate returns from them
            # Actually let's store returns directly
            pass

        # Store ATR if provided
        if atr_percent is not None:
            self._atr_history[symbol].append(float(atr_percent))

    def feed_return(self, symbol: str, return_pct: float):
        """Feed a return percentage directly."""
        if symbol not in self._returns_history:
            self._returns_history[symbol] = deque(maxlen=self.lookback)
        self._returns_history[symbol].append(float(return_pct))

    def forecast_atr(self, symbol: str, current_atr: float = None, horizon: int = 5) -> Dict[str, Any]:
        """Forecast ATR for next N bars."""
        returns = list(self._returns_history.get(symbol, []))
        atrs = list(self._atr_history.get(symbol, []))

        if len(returns) < 10:
            # Not enough data — return current with small adjustment
            return {
                "forecast_atr": current_atr or 1.0,
                "confidence": 0.3,
                "trend": "stable",
                "method": "insufficient_data"
            }

        # EWMA volatility
        lambda_ = 0.94
        ewma_var = returns[0] ** 2
        for r in returns[1:]:
            ewma_var = lambda_ * ewma_var + (1 - lambda_) * (r ** 2)
        ewma_vol = math.sqrt(ewma_var)

        # Trend in ATR
        if len(atrs) >= 5:
            recent_avg = sum(atrs[-5:]) / 5
            older_avg = sum(atrs[-10:-5]) / 5 if len(atrs) >= 10 else recent_avg
            atr_trend = (recent_avg - older_avg) / max(older_avg, 0.001)
        else:
            atr_trend = 0
            recent_avg = current_atr or 1.0

        # Forecast: combine EWMA trend with ATR trend
        forecast = recent_avg * (1 + atr_trend * 0.5)

        # Adjust for volatility regime
        returns_arr = np.array(returns)
        vol_mean = np.mean(np.abs(returns_arr))
        vol_std = np.std(returns_arr)

        if vol_std > vol_mean * 1.5:
            # High volatility regime — forecast higher
            forecast *= 1.2
            trend = "rising"
        elif vol_std < vol_mean * 0.5:
            # Low volatility — forecast lower
            forecast *= 0.9
            trend = "falling"
        else:
            trend = "stable"

        confidence = min(1.0, len(returns) / self.lookback)

        self._forecasts[symbol] = {
            "forecast": forecast,
            "current": current_atr,
            "trend": trend,
            "confidence": confidence,
            "time": time.time()
        }

        return {
            "forecast_atr": round(forecast, 4),
            "confidence": round(confidence, 2),
            "trend": trend,
            "method": "ewma_garch_like",
            "ewma_volatility": round(ewma_vol, 4),
            "samples": len(returns)
        }

    def get_position_size_adjustment(self, symbol: str) -> float:
        """Return multiplier for position size based on volatility forecast."""
        forecast = self._forecasts.get(symbol)
        if not forecast:
            return 1.0

        f_atr = forecast["forecast"]
        c_atr = forecast.get("current", f_atr)

        if c_atr <= 0:
            return 1.0

        ratio = f_atr / c_atr

        if ratio > 1.5:
            # Volatility rising — reduce size
            return max(0.3, 1.0 / ratio)
        elif ratio < 0.7:
            # Volatility falling — can increase size slightly
            return min(1.3, 1.0 / ratio)
        return 1.0

    def should_avoid_symbol(self, symbol: str, threshold: float = 5.0) -> bool:
        """Avoid symbols with exploding volatility."""
        forecast = self._forecasts.get(symbol)
        if not forecast:
            return False
        return forecast["forecast"] > threshold

    def get_stats(self, symbol: str = None) -> Dict[str, Any]:
        if symbol:
            return self._forecasts.get(symbol, {})
        return {
            "symbols_tracked": len(self._returns_history),
            "forecasts_made": len(self._forecasts),
            "samples_per_symbol": {k: len(v) for k, v in self._returns_history.items()}
        }
