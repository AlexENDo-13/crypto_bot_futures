"""
Volume Breakout Strategy - Momentum on volume expansion.
"""
import pandas as pd
from src.plugins.strategy_base import BaseStrategy, Signal

class VolumeBreakoutStrategy(BaseStrategy):
    name = "volume_breakout"

    def analyze(self, symbol, df, timeframe_data):
        if len(df) < 2:
            return None

        latest = df.iloc[-1]
        prev = df.iloc[-2]
        price = float(latest["close"])
        vol_ratio = float(latest.get("volume_ratio", 1))

        if vol_ratio < 2.0:
            return None

        change = (latest["close"] - prev["close"]) / prev["close"] * 100

        if change > 0.5:
            conf = 0.6 + min(vol_ratio / 10, 0.2)
            return Signal(symbol, "LONG", min(conf, 0.9), self.name, "15m",
                         price, price * 0.99, price * 1.02, f"Vol breakout {vol_ratio:.1f}x +{change:.2f}%")
        elif change < -0.5:
            conf = 0.6 + min(vol_ratio / 10, 0.2)
            return Signal(symbol, "SHORT", min(conf, 0.9), self.name, "15m",
                         price, price * 1.01, price * 0.98, f"Vol breakout {vol_ratio:.1f}x {change:.2f}%")

        return None
