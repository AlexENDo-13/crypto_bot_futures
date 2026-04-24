"""
MACD Momentum Strategy - Momentum confirmation with histogram.
"""
import pandas as pd
from src.plugins.strategy_base import BaseStrategy, Signal

class MACDMomentumStrategy(BaseStrategy):
    name = "macd_momentum"

    def analyze(self, symbol, df, timeframe_data):
        if len(df) < 5:
            return None

        latest = df.iloc[-1]
        prev = df.iloc[-2]
        prev2 = df.iloc[-3] if len(df) > 2 else prev
        price = float(latest["close"])

        hist = latest.get("macd_hist", 0)
        prev_hist = prev.get("macd_hist", 0)
        prev2_hist = prev2.get("macd_hist", 0)

        # Bullish: histogram turning positive and expanding
        if hist > 0 and prev_hist <= 0:
            conf = 0.65
            if latest.get("volume_ratio", 1) > 1.2: conf += 0.1
            return Signal(symbol, "LONG", min(conf, 0.9), self.name, "15m",
                         price, price * 0.99, price * 1.02, "MACD histogram bullish flip")

        # Bearish: histogram turning negative
        if hist < 0 and prev_hist >= 0:
            conf = 0.65
            if latest.get("volume_ratio", 1) > 1.2: conf += 0.1
            return Signal(symbol, "SHORT", min(conf, 0.9), self.name, "15m",
                         price, price * 1.01, price * 0.98, "MACD histogram bearish flip")

        return None
