"""
Bollinger Squeeze Strategy - Volatility expansion after contraction.
"""
import pandas as pd
from src.plugins.strategy_base import BaseStrategy, Signal

class BollingerSqueezeStrategy(BaseStrategy):
    name = "bollinger_squeeze"

    def analyze(self, symbol, df, timeframe_data):
        if len(df) < 25:
            return None

        latest = df.iloc[-1]
        prev = df.iloc[-2]
        price = float(latest["close"])

        # Check for squeeze release
        was_squeezed = prev.get("bb_squeeze", False)
        is_squeezed = latest.get("bb_squeeze", False)

        if was_squeezed and not is_squeezed:
            bb_pos = latest.get("bb_position", 0.5)

            if bb_pos < 0.3:
                conf = 0.65
                return Signal(symbol, "LONG", min(conf, 0.9), self.name, "15m",
                             price, price * 0.99, price * 1.025, "BB squeeze breakout up")
            elif bb_pos > 0.7:
                conf = 0.65
                return Signal(symbol, "SHORT", min(conf, 0.9), self.name, "15m",
                             price, price * 1.01, price * 0.975, "BB squeeze breakout down")

        return None
