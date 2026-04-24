"""
EMA Cross Strategy - Classic trend following with multi-EMA confirmation.
"""
import pandas as pd
from typing import Dict, Optional
from src.plugins.strategy_base import BaseStrategy, Signal

class EMACrossStrategy(BaseStrategy):
    name = "ema_cross"

    def analyze(self, symbol, df, timeframe_data):
        if len(df) < 5:
            return None

        latest = df.iloc[-1]
        prev = df.iloc[-2]
        price = float(latest["close"])

        fast_above = latest["ema_fast"] > latest["ema_slow"]
        prev_fast_above = prev["ema_fast"] > prev["ema_slow"]

        if fast_above and not prev_fast_above:
            conf = 0.6
            if price > latest.get("ema_trend", 0): conf += 0.1
            if price > latest.get("ema_long", 0): conf += 0.1
            if latest.get("volume_ratio", 1) > 1.5: conf += 0.05

            return Signal(symbol, "LONG", min(conf, 0.95), self.name, "15m",
                         price, price * 0.99, price * 1.02, "EMA bullish cross")

        elif not fast_above and prev_fast_above:
            conf = 0.6
            if price < latest.get("ema_trend", float("inf")): conf += 0.1
            if price < latest.get("ema_long", float("inf")): conf += 0.1
            if latest.get("volume_ratio", 1) > 1.5: conf += 0.05

            return Signal(symbol, "SHORT", min(conf, 0.95), self.name, "15m",
                         price, price * 1.01, price * 0.98, "EMA bearish cross")

        return None
