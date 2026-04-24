"""
RSI Strategy - Mean reversion with divergence detection.
"""
import pandas as pd
from typing import Dict, Optional
from src.plugins.strategy_base import BaseStrategy, Signal

class RSIStrategy(BaseStrategy):
    name = "rsi_divergence"

    def analyze(self, symbol, df, timeframe_data):
        if len(df) < 20:
            return None

        latest = df.iloc[-1]
        prev = df.iloc[-2]
        price = float(latest["close"])
        rsi = float(latest["rsi"])

        if rsi < 30:
            conf = 0.55 + (30 - rsi) / 100
            if latest.get("macd_hist", 0) > prev.get("macd_hist", 0):
                conf += 0.1
            return Signal(symbol, "LONG", min(conf, 0.9), self.name, "15m",
                         price, price * 0.985, price * 1.025, f"RSI oversold {rsi:.1f}")

        elif rsi > 70:
            conf = 0.55 + (rsi - 70) / 100
            if latest.get("macd_hist", 0) < prev.get("macd_hist", 0):
                conf += 0.1
            return Signal(symbol, "SHORT", min(conf, 0.9), self.name, "15m",
                         price, price * 1.015, price * 0.975, f"RSI overbought {rsi:.1f}")

        return None
